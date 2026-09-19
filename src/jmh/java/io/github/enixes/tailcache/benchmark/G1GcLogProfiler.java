package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.profile.ExternalProfiler;
import org.openjdk.jmh.results.AggregationPolicy;
import org.openjdk.jmh.results.BenchmarkResult;
import org.openjdk.jmh.results.Result;
import org.openjdk.jmh.results.ScalarResult;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Retains one raw HotSpot G1 log per JMH fork and derives stop-the-world pause metrics.
 *
 * <p>Only completed {@code Pause ... <duration>} records whose System.nanoTime timestamps fall inside one of
 * the exact measurement-iteration windows recorded by {@link GcMeasurementWindowProfiler} are
 * counted. Concurrent G1 cycle lines are therefore retained in the raw log but excluded from pause
 * totals.</p>
 */
public final class G1GcLogProfiler implements ExternalProfiler {

    private static final Pattern LOG_LINE = Pattern.compile(
            "^\\[([0-9]+)ns\\]\\[info\\]\\[gc\\s*\\]\\s+(.*)$"
    );
    private static final Pattern PAUSE_LINE = Pattern.compile(
            "^GC\\(\\d+\\)\\s+Pause\\b.*\\s([0-9]+(?:[\\.,][0-9]+)?)(ns|us|ms|s)$"
    );

    private final Path outputDirectory;

    public G1GcLogProfiler() {
        this("");
    }

    public G1GcLogProfiler(String initLine) {
        this.outputDirectory = parseOutputDirectory(initLine);
        try {
            Files.createDirectories(outputDirectory);
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to create GC log directory " + outputDirectory, exception);
        }
    }

    @Override
    public String getDescription() {
        return "TailCache G1 pause metrics plus raw unified GC log retention";
    }

    @Override
    public Collection<String> addJVMInvokeOptions(BenchmarkParams params) {
        return Collections.emptyList();
    }

    @Override
    public Collection<String> addJVMOptions(BenchmarkParams params) {
        Path logPath = GcProfileFiles.gcLogTemplate(outputDirectory, params);
        return List.of(
                "-Xlog:gc=info:file=" + logPath + ":timenanos,level,tags:filecount=0"
        );
    }

    @Override
    public void beforeTrial(BenchmarkParams benchmarkParams) {
        // HotSpot opens the configured log when the fork starts.
    }

    @Override
    public Collection<? extends Result> afterTrial(
            BenchmarkResult benchmarkResult,
            long pid,
            File stdOut,
            File stdErr
    ) {
        BenchmarkParams params = benchmarkResult.getParams();
        Path logPath = GcProfileFiles.gcLog(outputDirectory, params, pid);
        Path windowsPath = GcProfileFiles.measurementWindows(outputDirectory, params, pid);

        List<MeasurementWindow> windows = readMeasurementWindows(\n                windowsPath,\n                params.getMeasurement().getCount()\n        );
        PauseSummary summary = parsePauses(logPath, windows);

        return List.of(
                new ScalarResult(
                        "gc.pause.count",
                        summary.count(),
                        "pauses",
                        AggregationPolicy.SUM
                ),
                new ScalarResult(
                        "gc.pause.time",
                        summary.totalMs(),
                        "ms",
                        AggregationPolicy.SUM
                ),
                new ScalarResult(
                        "gc.pause.max",
                        summary.maxMs(),
                        "ms",
                        AggregationPolicy.MAX
                )
        );
    }

    @Override
    public boolean allowPrintOut() {
        return true;
    }

    @Override
    public boolean allowPrintErr() {
        return true;
    }

    private static List<MeasurementWindow> readMeasurementWindows(Path path, int expectedCount) {
        if (!Files.isRegularFile(path)) {
            throw new IllegalStateException("Expected GC measurement windows were not created: " + path);
        }

        List<MeasurementWindow> windows = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.isEmpty()) {
                    continue;
                }

                String[] parts = trimmed.split(",", -1);
                if (parts.length != 2) {
                    throw new IllegalStateException("Malformed GC measurement window: " + line);
                }
                long startMs = Long.parseLong(parts[0]);
                long endMs = Long.parseLong(parts[1]);
                if (endMs < startMs) {
                    throw new IllegalStateException("GC measurement window ends before it starts: " + line);
                }
                windows.add(new MeasurementWindow(startNanoTime, endNanoTime));
            }
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to read GC measurement windows " + path, exception);
        }

        if (windows.size() != expectedCount) {
            throw new IllegalStateException(
                    "Expected " + expectedCount + " measurement windows, found " + windows.size()
                            + " in " + path
            );
        }
        return windows;
    }


    private static PauseSummary parsePauses(Path logPath, List<MeasurementWindow> windows) {
        if (!Files.isRegularFile(logPath)) {
            throw new IllegalStateException("Expected raw G1 log was not created: " + logPath);
        }

        boolean g1Confirmed = false;
        long count = 0L;
        double totalMs = 0.0;
        double maxMs = 0.0;

        try (BufferedReader reader = Files.newBufferedReader(logPath, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                Matcher logMatcher = LOG_LINE.matcher(line.trim());
                if (!logMatcher.matches()) {
                    continue;
                }

                long eventNanoTime = Long.parseLong(logMatcher.group(1));
                String message = logMatcher.group(2);
                if (message.contains("Using G1")) {
                    g1Confirmed = true;
                }

                if (!insideAnyMeasurementWindow(eventNanoTime, windows)) {
                    continue;
                }

                Matcher pauseMatcher = PAUSE_LINE.matcher(message);
                if (!pauseMatcher.matches()) {
                    continue;
                }

                double pauseMs = toMilliseconds(
                        parseDecimal(pauseMatcher.group(1)),
                        pauseMatcher.group(2)
                );
                count++;
                totalMs += pauseMs;
                maxMs = Math.max(maxMs, pauseMs);
            }
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to parse raw G1 log " + logPath, exception);
        }

        if (!g1Confirmed) {
            throw new IllegalStateException(
                    "G1GcLogProfiler requires G1; no 'Using G1' marker found in " + logPath
            );
        }

        return new PauseSummary(count, totalMs, maxMs);
    }

    private static boolean insideAnyMeasurementWindow(
            long eventNanoTime,
            List<MeasurementWindow> windows
    ) {
        for (MeasurementWindow window : windows) {
            if (eventNanoTime >= window.startNanoTime() && eventNanoTime <= window.endNanoTime()) {
                return true;
            }
        }
        return false;
    }

    private static Path parseOutputDirectory(String initLine) {
        if (initLine == null || initLine.isBlank()) {
            return Path.of("build", "reports", "tailcache06", "gc");
        }

        for (String option : initLine.split(";")) {
            if (option.startsWith("dir=")) {
                String value = option.substring("dir=".length());
                if (value.isBlank()) {
                    throw new IllegalArgumentException("G1GcLogProfiler dir must not be blank");
                }
                return Path.of(value);
            }
        }
        throw new IllegalArgumentException("Unsupported G1GcLogProfiler options: " + initLine);
    }

    private static double parseDecimal(String value) {
        return Double.parseDouble(value.replace(',', '.'));
    }

    private static double toMilliseconds(double value, String unit) {
        return switch (unit.toLowerCase(Locale.ROOT)) {
            case "ns" -> value / 1_000_000.0;
            case "us" -> value / 1_000.0;
            case "ms" -> value;
            case "s" -> value * 1_000.0;
            default -> throw new IllegalArgumentException("Unknown duration unit: " + unit);
        };
    }

    private record MeasurementWindow(long startNanoTime, long endNanoTime) {
    }

    private record PauseSummary(long count, double totalMs, double maxMs) {
    }
}

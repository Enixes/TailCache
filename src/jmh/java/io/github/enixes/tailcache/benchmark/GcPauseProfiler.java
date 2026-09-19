package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.profile.ExternalProfiler;
import org.openjdk.jmh.results.AggregationPolicy;
import org.openjdk.jmh.results.BenchmarkResult;
import org.openjdk.jmh.results.BenchmarkResultMetaData;
import org.openjdk.jmh.results.Result;
import org.openjdk.jmh.results.ScalarResult;

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
 * G1-specific measurement-window GC pause profiler.
 *
 * <p>The profiler asks HotSpot unified logging for exact {@code gc} tag messages, writes one raw log
 * per fork, and parses only completed {@code Pause ... <duration>} records whose JVM-uptime
 * timestamps fall inside JMH's measurement window. It intentionally does not treat concurrent G1
 * phases as pauses.</p>
 *
 * <p>This is separate from JMH's built-in {@code gc} profiler. The built-in profiler supplies
 * allocation rate plus MXBean collection count/time; this profiler supplies stop-the-world pause
 * count/total/max from the retained G1 log.</p>
 */
public final class GcPauseProfiler implements ExternalProfiler {

    private static final Pattern LOG_LINE = Pattern.compile(
            "^\\[([0-9]+(?:[\\.,][0-9]+)?)ms\\]\\[info\\]\\[gc\\s*\\]\\s+(.*)$"
    );
    private static final Pattern PAUSE_LINE = Pattern.compile(
            "^GC\\(\\d+\\)\\s+Pause\\b.*\\s([0-9]+(?:[\\.,][0-9]+)?)(ns|us|ms|s)$"
    );

    private final Path outputDirectory;

    public GcPauseProfiler() {
        this("");
    }

    public GcPauseProfiler(String initLine) {
        this.outputDirectory = parseOutputDirectory(initLine);
        try {
            Files.createDirectories(outputDirectory);
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to create GC log directory " + outputDirectory, exception);
        }
    }

    @Override
    public String getDescription() {
        return "TailCache G1 pause totals from measurement-window unified GC logs";
    }

    @Override
    public Collection<String> addJVMInvokeOptions(BenchmarkParams params) {
        return Collections.emptyList();
    }

    @Override
    public Collection<String> addJVMOptions(BenchmarkParams params) {
        Path logPath = outputDirectory.resolve(trialStem(params) + "-%p.log").toAbsolutePath();
        return List.of(
                "-Xlog:gc=info:file=" + logPath + ":uptimemillis,level,tags:filecount=0"
        );
    }

    @Override
    public void beforeTrial(BenchmarkParams benchmarkParams) {
        // Raw log creation is handled by HotSpot when the fork starts.
    }

    @Override
    public Collection<? extends Result> afterTrial(
            BenchmarkResult benchmarkResult,
            long pid,
            File stdOut,
            File stdErr
    ) {
        Path logPath = outputDirectory.resolve(trialStem(benchmarkResult.getParams()) + "-" + pid + ".log");
        PauseSummary summary = parseMeasurementWindow(logPath, benchmarkResult);

        List<Result> results = new ArrayList<>();
        results.add(new ScalarResult(
                "gc.pause.count",
                summary.count(),
                "pauses",
                AggregationPolicy.SUM
        ));
        results.add(new ScalarResult(
                "gc.pause.time",
                summary.totalMs(),
                "ms",
                AggregationPolicy.SUM
        ));
        results.add(new ScalarResult(
                "gc.pause.max",
                summary.maxMs(),
                "ms",
                AggregationPolicy.MAX
        ));
        return results;
    }

    @Override
    public boolean allowPrintOut() {
        return true;
    }

    @Override
    public boolean allowPrintErr() {
        return true;
    }

    private static PauseSummary parseMeasurementWindow(Path logPath, BenchmarkResult result) {
        if (!Files.isRegularFile(logPath)) {
            throw new IllegalStateException("Expected GC log was not created: " + logPath);
        }

        long measureFromMs = measurementDelayMs(result);
        long measureToMs = measureFromMs + measuredTimeMs(result);

        boolean g1Confirmed = false;
        long count = 0;
        double totalMs = 0.0;
        double maxMs = 0.0;

        try {
            for (String line : Files.readAllLines(logPath, StandardCharsets.UTF_8)) {
                Matcher logMatcher = LOG_LINE.matcher(line.trim());
                if (!logMatcher.matches()) {
                    continue;
                }

                double uptimeMs = parseDecimal(logMatcher.group(1));
                String message = logMatcher.group(2);
                if (message.contains("Using G1")) {
                    g1Confirmed = true;
                }

                if (!(uptimeMs > measureFromMs && uptimeMs < measureToMs)) {
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
            throw new IllegalStateException("Unable to parse GC log " + logPath, exception);
        }

        if (!g1Confirmed) {
            throw new IllegalStateException(
                    "GcPauseProfiler currently supports G1 only; no 'Using G1' marker in " + logPath
            );
        }

        return new PauseSummary(count, totalMs, maxMs);
    }

    private static long measurementDelayMs(BenchmarkResult result) {
        BenchmarkResultMetaData metadata = result.getMetadata();
        if (metadata != null) {
            return metadata.getMeasurementTime() - metadata.getStartTime();
        }

        IterationParams warmup = result.getParams().getWarmup();
        return warmup.getCount() * warmup.getTime().convertTo(TimeUnit.MILLISECONDS)
                + TimeUnit.SECONDS.toMillis(1);
    }

    private static long measuredTimeMs(BenchmarkResult result) {
        BenchmarkResultMetaData metadata = result.getMetadata();
        if (metadata != null) {
            return metadata.getStopTime() - metadata.getMeasurementTime();
        }

        IterationParams measurement = result.getParams().getMeasurement();
        return measurement.getCount() * measurement.getTime().convertTo(TimeUnit.MILLISECONDS);
    }

    private static Path parseOutputDirectory(String initLine) {
        if (initLine == null || initLine.isBlank()) {
            return Path.of("build", "reports", "tailcache06", "gc");
        }

        for (String option : initLine.split(";")) {
            if (option.startsWith("dir=")) {
                String value = option.substring("dir=".length());
                if (value.isBlank()) {
                    throw new IllegalArgumentException("GcPauseProfiler dir must not be blank");
                }
                return Path.of(value);
            }
        }
        throw new IllegalArgumentException("Unsupported GcPauseProfiler options: " + initLine);
    }

    private static String trialStem(BenchmarkParams params) {
        StringBuilder builder = new StringBuilder("gc-")
                .append(sanitize(params.getBenchmark()))
                .append("-")
                .append(params.getMode().shortLabel())
                .append("-t")
                .append(params.getThreads());

        params.getParamsKeys().stream().sorted().forEach(key -> builder
                .append("-")
                .append(sanitize(key))
                .append("-")
                .append(sanitize(params.getParam(key))));

        return builder.toString();
    }

    private static String sanitize(String value) {
        return value.replaceAll("[^A-Za-z0-9._-]+", "_");
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

    private record PauseSummary(long count, double totalMs, double maxMs) {
    }
}

package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.profile.InternalProfiler;
import org.openjdk.jmh.results.IterationResult;
import org.openjdk.jmh.results.Result;
import org.openjdk.jmh.runner.IterationType;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Collection;
import java.util.Collections;

/**
 * Records JMH internal-profiler envelopes for measurement iterations using
 * {@link System#nanoTime()}.
 *
 * <p>JMH starts internal profilers before worker submission and stops them after workers finish,
 * so these envelopes are intentionally a little wider than the configured timed workload interval.
 * They are used to attribute G1 pause log lines to the profiled measurement iteration, not to claim
 * exact per-operation timing boundaries. Warmup envelopes are deliberately not recorded.</p>
 */
public final class GcMeasurementWindowProfiler implements InternalProfiler {

    private final Path outputDirectory;
    private final long pid = ProcessHandle.current().pid();

    private long iterationStartNanoTime;
    private boolean measurementFileInitialized;

    public GcMeasurementWindowProfiler() {
        this("");
    }

    public GcMeasurementWindowProfiler(String initLine) {
        this.outputDirectory = parseOutputDirectory(initLine);
        try {
            Files.createDirectories(outputDirectory);
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "Unable to create GC measurement-window directory " + outputDirectory,
                    exception
            );
        }
    }

    @Override
    public String getDescription() {
        return "TailCache JMH measurement-iteration profiler-envelope recorder for G1 pause attribution";
    }

    @Override
    public void beforeIteration(BenchmarkParams benchmarkParams, IterationParams iterationParams) {
        if (iterationParams.getType() != IterationType.MEASUREMENT) {
            return;
        }

        Path windows = GcProfileFiles.measurementWindows(outputDirectory, benchmarkParams, pid);
        if (!measurementFileInitialized) {
            try {
                Files.deleteIfExists(windows);
            } catch (IOException exception) {
                throw new IllegalStateException(
                        "Unable to reset GC measurement windows " + windows,
                        exception
                );
            }
            measurementFileInitialized = true;
        }

        // Capture as the final action before returning to JMH's measured iteration.
        iterationStartNanoTime = System.nanoTime();
    }

    @Override
    public Collection<? extends Result> afterIteration(
            BenchmarkParams benchmarkParams,
            IterationParams iterationParams,
            IterationResult result
    ) {
        if (iterationParams.getType() != IterationType.MEASUREMENT) {
            return Collections.emptyList();
        }

        // Capture immediately on entry, before the sidecar write itself can perturb the next gap.
        long iterationEndNanoTime = System.nanoTime();
        Path windows = GcProfileFiles.measurementWindows(outputDirectory, benchmarkParams, pid);
        String line = iterationStartNanoTime + "," + iterationEndNanoTime + System.lineSeparator();

        try {
            Files.writeString(
                    windows,
                    line,
                    StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.APPEND
            );
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "Unable to write GC measurement window " + windows,
                    exception
            );
        }

        return Collections.emptyList();
    }

    private static Path parseOutputDirectory(String initLine) {
        if (initLine == null || initLine.isBlank()) {
            return Path.of("build", "reports", "tailcache06", "gc");
        }

        for (String option : initLine.split(";")) {
            if (option.startsWith("dir=")) {
                String value = option.substring("dir=".length());
                if (value.isBlank()) {
                    throw new IllegalArgumentException(
                            "GcMeasurementWindowProfiler dir must not be blank"
                    );
                }
                return Path.of(value);
            }
        }

        throw new IllegalArgumentException(
                "Unsupported GcMeasurementWindowProfiler options: " + initLine
        );
    }
}

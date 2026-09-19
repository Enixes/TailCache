package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.profile.ExternalProfiler;
import org.openjdk.jmh.results.BenchmarkResult;
import org.openjdk.jmh.results.Result;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collection;
import java.util.Collections;
import java.util.List;

/**
 * Retains one raw HotSpot GC log per JMH fork for TailCache's profiled runs.
 *
 * <p>The log is audit evidence, not the source of the summary pause metrics. Pause metrics come from
 * {@link GcPauseProfiler}, whose notification timing is aligned to individual JMH iterations.</p>
 */
public final class G1GcLogProfiler implements ExternalProfiler {

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
        return "TailCache raw G1 unified GC log retention";
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
        // HotSpot opens the configured log when the fork starts.
    }

    @Override
    public Collection<? extends Result> afterTrial(
            BenchmarkResult benchmarkResult,
            long pid,
            File stdOut,
            File stdErr
    ) {
        Path logPath = outputDirectory.resolve(trialStem(benchmarkResult.getParams()) + "-" + pid + ".log");
        if (!Files.isRegularFile(logPath)) {
            throw new IllegalStateException("Expected raw G1 log was not created: " + logPath);
        }
        return Collections.emptyList();
    }

    @Override
    public boolean allowPrintOut() {
        return true;
    }

    @Override
    public boolean allowPrintErr() {
        return true;
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
}

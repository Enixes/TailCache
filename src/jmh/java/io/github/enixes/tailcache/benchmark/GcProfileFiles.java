package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.infra.BenchmarkParams;

import java.nio.file.Path;

final class GcProfileFiles {

    private GcProfileFiles() {
    }

    static Path gcLogTemplate(Path directory, BenchmarkParams params) {
        return directory.resolve(trialStem(params) + "-%p.log").toAbsolutePath();
    }

    static Path gcLog(Path directory, BenchmarkParams params, long pid) {
        return directory.resolve(trialStem(params) + "-" + pid + ".log").toAbsolutePath();
    }

    static Path measurementWindows(Path directory, BenchmarkParams params, long pid) {
        return directory.resolve(trialStem(params) + "-" + pid + ".windows.csv").toAbsolutePath();
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

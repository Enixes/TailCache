package io.github.enixes.tailcache.results;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Writes TailCache run provenance outside Gradle's task-action closure.
 *
 * <p>Keeping execution-time Git/process access in a regular Java program avoids capturing the
 * Kotlin build-script object in a {@code doLast} action, which is incompatible with Gradle's
 * configuration cache.</p>
 */
public final class TailCacheRunMetadataWriter {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    private TailCacheRunMetadataWriter() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> options = parseArgs(args);

        Path output = requiredPath(options, "--out");
        Path root = requiredPath(options, "--root");
        String benchmarkJava = required(options, "--benchmark-java");

        String gitCommit = commandOutput(root, "git", "rev-parse", "HEAD");
        String gitStatus = commandOutput(root, "git", "status", "--porcelain");

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("schemaVersion", "tailcache-run-metadata-v1");
        metadata.put("generatedAtUtc", Instant.now().toString());
        metadata.put("runKind", required(options, "--run-kind"));
        metadata.put("runId", required(options, "--run-id"));
        metadata.put("gitCommit", gitCommit);
        metadata.put("gitDirty", !gitStatus.isBlank());
        metadata.put("gitStatusPorcelain", gitStatus);
        metadata.put("benchmarkJavaExecutable", benchmarkJava);
        metadata.put(
                "benchmarkJavaVersion",
                commandOutput(root, benchmarkJava, "-version")
        );
        metadata.put("gradleVersion", required(options, "--gradle-version"));
        metadata.put("jmhVersion", required(options, "--jmh-version"));
        metadata.put("caffeineVersion", required(options, "--caffeine-version"));
        metadata.put("chronicleMapVersion", required(options, "--chronicle-version"));
        metadata.put("jacksonResultToolVersion", required(options, "--jackson-version"));
        metadata.put("modes", required(options, "--modes"));
        metadata.put("threads", required(options, "--threads"));
        metadata.put("collector", "G1");

        Map<String, String> metricSources = new LinkedHashMap<>();
        metricSources.put("latency", "unprofiled JMH SampleTime");
        metricSources.put("throughput", "unprofiled JMH Throughput");
        metricSources.put("allocationAndCollection", "JMH gc profiler via MXBeans");
        metricSources.put(
                "gcPauses",
                "JMH measurement-iteration internal-profiler envelopes + G1 -Xlog:gc=info timenanos Pause records"
        );
        metadata.put("metricSources", metricSources);

        metadata.put(
                "rawFiles",
                List.of(
                        "latency.json",
                        "latency.txt",
                        "throughput.json",
                        "throughput.txt",
                        "gc-profile.json",
                        "gc-profile.txt",
                        "gc/*.log",
                        "gc/*.windows.csv"
                )
        );

        Files.createDirectories(output.toAbsolutePath().getParent());
        MAPPER.writeValue(output.toFile(), metadata);
    }

    private static String commandOutput(Path root, String... command)
            throws IOException, InterruptedException {
        Process process = new ProcessBuilder(command)
                .directory(root.toFile())
                .redirectErrorStream(true)
                .start();

        String output;
        try (var reader = process.inputReader()) {
            output = reader.lines().reduce(
                    "",
                    (left, right) -> left.isEmpty() ? right : left + System.lineSeparator() + right
            );
        }

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new IllegalStateException(
                    "Command failed with exit code " + exitCode + ": "
                            + String.join(" ", command) + System.lineSeparator() + output
            );
        }
        return output.trim();
    }

    private static Map<String, String> parseArgs(String[] args) {
        if (args.length % 2 != 0) {
            throw new IllegalArgumentException("Expected --name value argument pairs");
        }

        Map<String, String> parsed = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i += 2) {
            String previous = parsed.put(args[i], args[i + 1]);
            if (previous != null) {
                throw new IllegalArgumentException("Duplicate option " + args[i]);
            }
        }
        return parsed;
    }

    private static String required(Map<String, String> options, String option) {
        String value = options.get(option);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing required option " + option);
        }
        return value;
    }

    private static Path requiredPath(Map<String, String> options, String option) {
        return Path.of(required(options, option));
    }
}

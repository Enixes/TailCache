package io.github.enixes.tailcache.results;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Joins the three TailCache 06 JMH runs into a compact analysis-ready result set.
 *
 * <p>Latency comes from an unprofiled SampleTime run, throughput from a separate unprofiled
 * Throughput run, and allocation/GC metrics from a third profiled run. Keeping these runs separate
 * prevents GC instrumentation and unified-log I/O from contaminating the latency percentiles that
 * answer the primary research question.</p>
 */
public final class TailCacheResultSummarizer {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    private TailCacheResultSummarizer() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> options = parseArgs(args);

        Path latencyPath = requiredPath(options, "--latency");
        Path throughputPath = requiredPath(options, "--throughput");
        Path gcPath = requiredPath(options, "--gc");
        Path metadataPath = requiredPath(options, "--metadata");
        Path outputJson = requiredPath(options, "--out-json");
        Path outputCsv = requiredPath(options, "--out-csv");

        ArrayNode latencyRuns = readArray(latencyPath);
        Map<RunKey, JsonNode> throughputRuns = index(readArray(throughputPath));
        Map<RunKey, JsonNode> gcRuns = index(readArray(gcPath));

        ObjectNode root = MAPPER.createObjectNode();
        root.put("schemaVersion", "tailcache-results-v1");
        root.put("generatedAtUtc", Instant.now().toString());
        root.set("runMetadata", MAPPER.readTree(metadataPath.toFile()));

        ArrayNode notes = root.putArray("notes");
        notes.add("Latency percentiles are from an unprofiled JMH SampleTime run.");
        notes.add("Throughput is from a separate unprofiled JMH Throughput run.");
        notes.add("Allocation and GC metrics are from a separate profiled run with JMH gc + TailCache G1 pause logging.");
        notes.add("gc.time is MXBean-reported collection time; gc.pause.time is the summed G1 stop-the-world Pause records in the measurement window.");

        ArrayNode rows = root.putArray("rows");
        List<ObjectNode> csvRows = new ArrayList<>();

        for (JsonNode latencyRun : latencyRuns) {
            RunKey key = RunKey.from(latencyRun);
            JsonNode throughputRun = requireMatch(throughputRuns, key, "throughput");
            JsonNode gcRun = requireMatch(gcRuns, key, "gc");

            ObjectNode row = buildRow(latencyRun, throughputRun, gcRun);
            rows.add(row);
            csvRows.add(row);
        }

        Files.createDirectories(outputJson.toAbsolutePath().getParent());
        MAPPER.writeValue(outputJson.toFile(), root);
        writeCsv(outputCsv, csvRows);
    }

    private static ObjectNode buildRow(JsonNode latencyRun, JsonNode throughputRun, JsonNode gcRun) {
        ObjectNode row = MAPPER.createObjectNode();
        row.put("benchmark", text(latencyRun, "benchmark"));
        row.put("threads", latencyRun.path("threads").asInt());

        ObjectNode params = row.putObject("params");
        latencyRun.path("params").fields().forEachRemaining(entry ->
                params.put(entry.getKey(), entry.getValue().asText())
        );

        JsonNode latencyMetric = latencyRun.path("primaryMetric");
        ObjectNode latency = row.putObject("latency");
        latency.put("unit", text(latencyMetric, "scoreUnit"));
        putNumber(latency, "p50", percentile(latencyMetric, "50.0"));
        putNumber(latency, "p95", percentile(latencyMetric, "95.0"));
        putNumber(latency, "p99", percentile(latencyMetric, "99.0"));
        putNumber(latency, "p99_9", percentile(latencyMetric, "99.9"));
        latency.put("sampleCount", histogramSampleCount(latencyMetric.path("rawDataHistogram")));

        ObjectNode throughput = row.putObject("throughput");
        putNumber(throughput, "score", number(throughputRun.path("primaryMetric").path("score")));
        throughput.put("unit", text(throughputRun.path("primaryMetric"), "scoreUnit"));

        JsonNode secondary = gcRun.path("secondaryMetrics");

        ObjectNode allocation = row.putObject("allocation");
        putNumber(allocation, "mbPerSec", metricScore(secondary, "gc.alloc.rate"));
        putNumber(allocation, "bytesPerOp", metricScore(secondary, "gc.alloc.rate.norm"));

        ObjectNode gc = row.putObject("gc");
        putNumber(gc, "collectionCount", metricScore(secondary, "gc.count"));
        putNumber(gc, "collectionTimeMs", metricScore(secondary, "gc.time"));
        putNumber(gc, "pauseCount", metricScore(secondary, "gc.pause.count"));
        putNumber(gc, "pauseTotalMs", metricScore(secondary, "gc.pause.time"));
        putNumber(gc, "pauseMaxMs", metricScore(secondary, "gc.pause.max"));

        ObjectNode metadata = row.putObject("jmhMetadata");
        copyText(latencyRun, metadata, "jmhVersion");
        copyText(latencyRun, metadata, "jvm");
        copyText(latencyRun, metadata, "jdkVersion");
        copyText(latencyRun, metadata, "vmName");
        copyText(latencyRun, metadata, "vmVersion");
        metadata.put("forks", latencyRun.path("forks").asInt());
        metadata.put("warmupIterations", latencyRun.path("warmupIterations").asInt());
        metadata.put("warmupTime", text(latencyRun, "warmupTime"));
        metadata.put("measurementIterations", latencyRun.path("measurementIterations").asInt());
        metadata.put("measurementTime", text(latencyRun, "measurementTime"));
        metadata.set("jvmArgs", latencyRun.path("jvmArgs").deepCopy());

        return row;
    }

    private static Map<RunKey, JsonNode> index(ArrayNode runs) {
        Map<RunKey, JsonNode> indexed = new LinkedHashMap<>();
        for (JsonNode run : runs) {
            RunKey key = RunKey.from(run);
            JsonNode previous = indexed.put(key, run);
            if (previous != null) {
                throw new IllegalStateException("Duplicate JMH record for " + key);
            }
        }
        return indexed;
    }

    private static JsonNode requireMatch(Map<RunKey, JsonNode> indexed, RunKey key, String source) {
        JsonNode match = indexed.get(key);
        if (match == null) {
            throw new IllegalStateException("Missing " + source + " JMH record for " + key);
        }
        return match;
    }

    private static ArrayNode readArray(Path path) throws IOException {
        JsonNode root = MAPPER.readTree(path.toFile());
        if (!(root instanceof ArrayNode arrayNode)) {
            throw new IllegalArgumentException("Expected JMH JSON array in " + path);
        }
        return arrayNode;
    }

    private static Double percentile(JsonNode primaryMetric, String percentile) {
        return number(primaryMetric.path("scorePercentiles").path(percentile));
    }

    private static Double metricScore(JsonNode secondaryMetrics, String metric) {
        return number(secondaryMetrics.path(metric).path("score"));
    }

    private static Double number(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        if (node.isNumber()) {
            return node.asDouble();
        }
        if (node.isTextual()) {
            String text = node.asText();
            if ("NaN".equals(text) || "+INF".equals(text) || "-INF".equals(text)) {
                return null;
            }
        }
        throw new IllegalArgumentException("Expected numeric JMH value, found " + node);
    }

    private static void putNumber(ObjectNode node, String field, Double value) {
        if (value == null) {
            node.putNull(field);
        } else {
            node.put(field, value);
        }
    }

    private static long histogramSampleCount(JsonNode node) {
        if (!node.isArray()) {
            return 0L;
        }
        if (node.size() == 2 && node.get(0).isNumber() && node.get(1).canConvertToLong()) {
            return node.get(1).asLong();
        }

        long total = 0L;
        for (JsonNode child : node) {
            total += histogramSampleCount(child);
        }
        return total;
    }

    private static void copyText(JsonNode source, ObjectNode destination, String field) {
        destination.put(field, text(source, field));
    }

    private static String text(JsonNode node, String field) {
        JsonNode child = node.path(field);
        return child.isMissingNode() || child.isNull() ? "" : child.asText();
    }

    private static Map<String, String> parseArgs(String[] args) {
        if (args.length % 2 != 0) {
            throw new IllegalArgumentException("Expected --name value argument pairs");
        }

        Map<String, String> parsed = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i += 2) {
            parsed.put(args[i], args[i + 1]);
        }
        return parsed;
    }

    private static Path requiredPath(Map<String, String> options, String option) {
        String value = options.get(option);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing required option " + option);
        }
        return Path.of(value);
    }

    private static void writeCsv(Path path, List<ObjectNode> rows) throws IOException {
        Files.createDirectories(path.toAbsolutePath().getParent());

        List<String> headers = List.of(
                "mode", "payloadSize", "accessPattern", "readWriteMix", "threads",
                "p50", "p95", "p99", "p99_9", "latencyUnit", "latencySampleCount",
                "throughput", "throughputUnit",
                "allocMBPerSec", "allocBytesPerOp",
                "gcCollectionCount", "gcCollectionTimeMs",
                "gcPauseCount", "gcPauseTotalMs", "gcPauseMaxMs",
                "jdkVersion", "vmName", "vmVersion", "forks"
        );

        try (BufferedWriter writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
            writer.write(String.join(",", headers));
            writer.newLine();

            for (ObjectNode row : rows) {
                JsonNode params = row.path("params");
                List<String> values = List.of(
                        csv(params.path("mode").asText()),
                        csv(params.path("payloadSize").asText()),
                        csv(params.path("accessPattern").asText()),
                        csv(params.path("readWriteMix").asText()),
                        csv(row.path("threads").asText()),
                        csv(value(row, "/latency/p50")),
                        csv(value(row, "/latency/p95")),
                        csv(value(row, "/latency/p99")),
                        csv(value(row, "/latency/p99_9")),
                        csv(value(row, "/latency/unit")),
                        csv(value(row, "/latency/sampleCount")),
                        csv(value(row, "/throughput/score")),
                        csv(value(row, "/throughput/unit")),
                        csv(value(row, "/allocation/mbPerSec")),
                        csv(value(row, "/allocation/bytesPerOp")),
                        csv(value(row, "/gc/collectionCount")),
                        csv(value(row, "/gc/collectionTimeMs")),
                        csv(value(row, "/gc/pauseCount")),
                        csv(value(row, "/gc/pauseTotalMs")),
                        csv(value(row, "/gc/pauseMaxMs")),
                        csv(value(row, "/jmhMetadata/jdkVersion")),
                        csv(value(row, "/jmhMetadata/vmName")),
                        csv(value(row, "/jmhMetadata/vmVersion")),
                        csv(value(row, "/jmhMetadata/forks"))
                );
                writer.write(String.join(",", values));
                writer.newLine();
            }
        }
    }

    private static String value(JsonNode node, String pointer) {
        JsonNode value = node.at(pointer);
        return value.isMissingNode() || value.isNull() ? "" : value.asText();
    }

    private static String csv(String value) {
        String escaped = value.replace(""", """");
        return """ + escaped + """;
    }

    private record RunKey(String benchmark, int threads, Map<String, String> params) {
        static RunKey from(JsonNode node) {
            Map<String, String> params = new TreeMap<>();
            node.path("params").fields().forEachRemaining(entry ->
                    params.put(entry.getKey(), entry.getValue().asText())
            );
            return new RunKey(node.path("benchmark").asText(), node.path("threads").asInt(), params);
        }
    }
}

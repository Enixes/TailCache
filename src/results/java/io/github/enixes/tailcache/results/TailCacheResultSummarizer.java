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
 * Throughput run, and allocation/GC metrics from a third profiled Throughput run. Keeping these
 * runs separate prevents profiler and GC-log instrumentation from contaminating the latency
 * percentiles that answer the primary research question.</p>
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
        ArrayNode throughputArray = readArray(throughputPath);
        ArrayNode gcArray = readArray(gcPath);

        validateSource(latencyRuns, "sample", "ns/op", "latency");
        validateSource(throughputArray, "thrpt", "ops/s", "throughput");
        validateSource(gcArray, "thrpt", "ops/s", "gc-profile");

        Map<RunKey, JsonNode> throughputRuns = index(throughputArray);
        Map<RunKey, JsonNode> gcRuns = index(gcArray);

        if (latencyRuns.size() != throughputRuns.size()
                || latencyRuns.size() != gcRuns.size()) {
            throw new IllegalStateException(
                    "JMH source cardinality mismatch: latency=" + latencyRuns.size()
                            + ", throughput=" + throughputRuns.size()
                            + ", gc=" + gcRuns.size()
            );
        }

        ObjectNode root = MAPPER.createObjectNode();
        root.put("schemaVersion", "tailcache-results-v1");
        root.put("generatedAtUtc", Instant.now().toString());
        root.set("runMetadata", MAPPER.readTree(metadataPath.toFile()));

        ArrayNode notes = root.putArray("notes");
        notes.add("Latency percentiles are from an unprofiled JMH SampleTime run.");
        notes.add("Throughput is from a separate unprofiled JMH Throughput run.");
        notes.add("Allocation and collector metrics are from a separate profiled Throughput run.");
        notes.add("gc.time is MXBean-reported collection time; gc.pause.time is summed G1 Pause log duration inside JMH measurement-iteration internal-profiler envelopes.");
        notes.add("The three runs share parameterization but are not event-by-event correlated.");

        ArrayNode rows = root.putArray("rows");
        List<ObjectNode> csvRows = new ArrayList<>();

        for (JsonNode latencyRun : latencyRuns) {
            RunKey key = RunKey.from(latencyRun);
            JsonNode throughputRun = requireMatch(throughputRuns, key, "throughput");
            JsonNode gcRun = requireMatch(gcRuns, key, "gc");

            validateComparableSettings(latencyRun, throughputRun, gcRun, key);

            ObjectNode row = buildRow(latencyRun, throughputRun, gcRun);
            rows.add(row);
            csvRows.add(row);
        }

        root.put("rowCount", rows.size());

        Files.createDirectories(outputJson.toAbsolutePath().getParent());
        MAPPER.writeValue(outputJson.toFile(), root);
        writeCsv(outputCsv, csvRows);
    }

    private static ObjectNode buildRow(
            JsonNode latencyRun,
            JsonNode throughputRun,
            JsonNode gcRun
    ) {
        ObjectNode row = MAPPER.createObjectNode();
        row.put("benchmark", requiredText(latencyRun, "benchmark"));
        row.put("threads", latencyRun.path("threads").asInt());

        ObjectNode params = row.putObject("params");
        latencyRun.path("params").properties().forEach(entry ->
                params.put(entry.getKey(), entry.getValue().asText())
        );

        JsonNode latencyMetric = latencyRun.path("primaryMetric");
        long sampleCount = histogramSampleCount(latencyMetric.path("rawDataHistogram"));
        if (sampleCount <= 0L) {
            throw new IllegalStateException(
                    "No retained SampleTime observations for " + RunKey.from(latencyRun)
            );
        }

        ObjectNode latency = row.putObject("latency");
        latency.put("unit", requiredText(latencyMetric, "scoreUnit"));
        latency.put("sampleCount", sampleCount);
        latency.put("p50", requiredPercentile(latencyMetric, "50.0"));
        latency.put("p95", requiredPercentile(latencyMetric, "95.0"));
        latency.put("p99", requiredPercentile(latencyMetric, "99.0"));
        latency.put("p99_9", requiredPercentile(latencyMetric, "99.9"));

        JsonNode throughputMetric = throughputRun.path("primaryMetric");
        ObjectNode throughput = row.putObject("throughput");
        throughput.put("score", requiredNumber(throughputMetric.path("score"), "throughput score"));
        throughput.put("unit", requiredText(throughputMetric, "scoreUnit"));

        JsonNode secondary = gcRun.path("secondaryMetrics");

        ObjectNode allocation = row.putObject("allocation");
        putOptionalNumber(allocation, "mbPerSec", metricScore(secondary, "gc.alloc.rate"));
        putOptionalNumber(allocation, "bytesPerOp", metricScore(secondary, "gc.alloc.rate.norm"));
        allocation.put("mbPerSecUnit", metricUnit(secondary, "gc.alloc.rate"));
        allocation.put("bytesPerOpUnit", metricUnit(secondary, "gc.alloc.rate.norm"));

        ObjectNode gc = row.putObject("gc");
        gc.put("collectionCount", requiredMetricScore(secondary, "gc.count"));
        putOptionalNumber(gc, "collectionTimeMs", metricScore(secondary, "gc.time"));
        gc.put("pauseCount", requiredMetricScore(secondary, "gc.pause.count"));
        gc.put("pauseTotalMs", requiredMetricScore(secondary, "gc.pause.time"));
        gc.put("pauseMaxMs", requiredMetricScore(secondary, "gc.pause.max"));
        gc.put("collectionCountUnit", metricUnit(secondary, "gc.count"));
        gc.put("collectionTimeUnit", metricUnit(secondary, "gc.time"));
        gc.put("pauseCountUnit", metricUnit(secondary, "gc.pause.count"));
        gc.put("pauseTimeUnit", metricUnit(secondary, "gc.pause.time"));

        ObjectNode metadata = row.putObject("jmhMetadata");
        copyText(latencyRun, metadata, "jmhVersion");
        copyText(latencyRun, metadata, "jvm");
        copyText(latencyRun, metadata, "jdkVersion");
        copyText(latencyRun, metadata, "vmName");
        copyText(latencyRun, metadata, "vmVersion");
        metadata.put("forks", latencyRun.path("forks").asInt());
        metadata.put("warmupIterations", latencyRun.path("warmupIterations").asInt());
        metadata.put("warmupTime", requiredText(latencyRun, "warmupTime"));
        metadata.put("measurementIterations", latencyRun.path("measurementIterations").asInt());
        metadata.put("measurementTime", requiredText(latencyRun, "measurementTime"));
        metadata.set("latencyJvmArgs", latencyRun.path("jvmArgs").deepCopy());
        metadata.set("throughputJvmArgs", throughputRun.path("jvmArgs").deepCopy());
        metadata.set("gcProfileJvmArgs", gcRun.path("jvmArgs").deepCopy());

        return row;
    }

    private static void validateSource(
            ArrayNode runs,
            String expectedMode,
            String expectedUnit,
            String sourceName
    ) {
        if (runs.isEmpty()) {
            throw new IllegalStateException("No JMH records in " + sourceName + " source");
        }

        for (JsonNode run : runs) {
            String mode = requiredText(run, "mode");
            if (!expectedMode.equals(mode)) {
                throw new IllegalStateException(
                        sourceName + " expected JMH mode " + expectedMode + ", found " + mode
                                + " for " + RunKey.from(run)
                );
            }

            String unit = requiredText(run.path("primaryMetric"), "scoreUnit");
            if (!expectedUnit.equals(unit)) {
                throw new IllegalStateException(
                        sourceName + " expected score unit " + expectedUnit + ", found " + unit
                                + " for " + RunKey.from(run)
                );
            }
        }
    }

    private static void validateComparableSettings(
            JsonNode latencyRun,
            JsonNode throughputRun,
            JsonNode gcRun,
            RunKey key
    ) {
        for (String field : List.of(
                "threads",
                "forks",
                "warmupIterations",
                "warmupTime",
                "measurementIterations",
                "measurementTime"
        )) {
            String latencyValue = latencyRun.path(field).asText();
            String throughputValue = throughputRun.path(field).asText();
            String gcValue = gcRun.path(field).asText();

            if (!latencyValue.equals(throughputValue)
                    || !latencyValue.equals(gcValue)) {
                throw new IllegalStateException(
                        "JMH setting mismatch for " + key + " field=" + field
                                + " latency=" + latencyValue
                                + " throughput=" + throughputValue
                                + " gc=" + gcValue
                );
            }
        }

        String latencyJdk = requiredText(latencyRun, "jdkVersion");
        String throughputJdk = requiredText(throughputRun, "jdkVersion");
        String gcJdk = requiredText(gcRun, "jdkVersion");
        if (!latencyJdk.equals(throughputJdk) || !latencyJdk.equals(gcJdk)) {
            throw new IllegalStateException(
                    "JDK mismatch across TailCache 06 sources for " + key
            );
        }
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

    private static JsonNode requireMatch(
            Map<RunKey, JsonNode> indexed,
            RunKey key,
            String source
    ) {
        JsonNode match = indexed.get(key);
        if (match == null) {
            throw new IllegalStateException(
                    "Missing " + source + " JMH record for " + key
            );
        }
        return match;
    }

    private static ArrayNode readArray(Path path) throws IOException {
        JsonNode root = MAPPER.readTree(path.toFile());
        if (!(root instanceof ArrayNode arrayNode)) {
            throw new IllegalArgumentException(
                    "Expected JMH JSON array in " + path
            );
        }
        return arrayNode;
    }

    private static double requiredPercentile(
            JsonNode primaryMetric,
            String percentile
    ) {
        return requiredNumber(
                primaryMetric.path("scorePercentiles").path(percentile),
                "percentile " + percentile
        );
    }

    private static Double metricScore(JsonNode secondaryMetrics, String metric) {
        return optionalNumber(secondaryMetrics.path(metric).path("score"));
    }

    private static double requiredMetricScore(
            JsonNode secondaryMetrics,
            String metric
    ) {
        return requiredNumber(
                secondaryMetrics.path(metric).path("score"),
                "secondary metric " + metric
        );
    }

    private static String metricUnit(JsonNode secondaryMetrics, String metric) {
        JsonNode metricNode = secondaryMetrics.path(metric);
        if (metricNode.isMissingNode()) {
            return "";
        }
        return text(metricNode, "scoreUnit");
    }

    private static Double optionalNumber(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        if (node.isNumber()) {
            return node.asDouble();
        }
        if (node.isTextual()) {
            String value = node.asText();
            if ("NaN".equals(value) || "+INF".equals(value) || "-INF".equals(value)) {
                return null;
            }
        }
        throw new IllegalArgumentException(
                "Expected numeric JMH value, found " + node
        );
    }

    private static double requiredNumber(JsonNode node, String description) {
        Double value = optionalNumber(node);
        if (value == null) {
            throw new IllegalStateException(
                    "Missing/invalid required numeric value: " + description
            );
        }
        return value;
    }

    private static void putOptionalNumber(
            ObjectNode node,
            String field,
            Double value
    ) {
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

        if (node.size() == 2
                && node.get(0).isNumber()
                && node.get(1).canConvertToLong()) {
            return node.get(1).asLong();
        }

        long total = 0L;
        for (JsonNode child : node) {
            total += histogramSampleCount(child);
        }
        return total;
    }

    private static void copyText(
            JsonNode source,
            ObjectNode destination,
            String field
    ) {
        destination.put(field, requiredText(source, field));
    }

    private static String requiredText(JsonNode node, String field) {
        String value = text(node, field);
        if (value.isBlank()) {
            throw new IllegalStateException("Missing required JMH field " + field);
        }
        return value;
    }

    private static String text(JsonNode node, String field) {
        JsonNode child = node.path(field);
        return child.isMissingNode() || child.isNull() ? "" : child.asText();
    }

    private static Map<String, String> parseArgs(String[] args) {
        if (args.length % 2 != 0) {
            throw new IllegalArgumentException(
                    "Expected --name value argument pairs"
            );
        }

        Map<String, String> parsed = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i += 2) {
            String previous = parsed.put(args[i], args[i + 1]);
            if (previous != null) {
                throw new IllegalArgumentException(
                        "Duplicate option " + args[i]
                );
            }
        }
        return parsed;
    }

    private static Path requiredPath(
            Map<String, String> options,
            String option
    ) {
        String value = options.get(option);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                    "Missing required option " + option
            );
        }
        return Path.of(value);
    }

    private static void writeCsv(
            Path path,
            List<ObjectNode> rows
    ) throws IOException {
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

        try (BufferedWriter writer = Files.newBufferedWriter(
                path,
                StandardCharsets.UTF_8
        )) {
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
        return value.isMissingNode() || value.isNull()
                ? ""
                : value.asText();
    }

    private static String csv(String value) {
        String escaped = value.replace("\"", "\"\"");
        return "\"" + escaped + "\"";
    }

    private record RunKey(
            String benchmark,
            int threads,
            Map<String, String> params
    ) {
        static RunKey from(JsonNode node) {
            String benchmark = node.path("benchmark").asText();
            if (benchmark.isBlank()) {
                throw new IllegalStateException("JMH record missing benchmark name");
            }

            Map<String, String> params = new TreeMap<>();
            node.path("params").properties().forEach(entry ->
                    params.put(entry.getKey(), entry.getValue().asText())
            );
            return new RunKey(
                    benchmark,
                    node.path("threads").asInt(),
                    params
            );
        }
    }
}

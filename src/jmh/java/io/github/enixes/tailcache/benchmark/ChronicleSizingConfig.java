package io.github.enixes.tailcache.benchmark;

import net.openhft.chronicle.map.ChronicleMap;
import net.openhft.chronicle.map.ChronicleMapBuilder;

import java.io.IOException;
import java.nio.file.Path;

/** Isolated TailCache 09 builder; the primary cache adapter remains unchanged. */
public final class ChronicleSizingConfig {
    static final int ENTRIES_TARGET = 256;
    static final double MAX_BLOAT_FACTOR = 1.0;

    public enum Estimate {
        HALF, MATCH, DOUBLE, CONSTANT;

        int configuredSampleBytes(int actualPayloadBytes) {
            return switch (this) {
                case HALF -> actualPayloadBytes / 2;
                case MATCH, CONSTANT -> actualPayloadBytes;
                case DOUBLE -> actualPayloadBytes * 2;
            };
        }
    }

    private ChronicleSizingConfig() {
    }

    static ChronicleMap<Long, byte[]> create(int actualPayloadBytes, Estimate estimate,
                                               Path persistedPath) throws IOException {
        if (!Boolean.getBoolean("chronicle.analytics.disable")) {
            throw new IllegalStateException("Chronicle analytics must be disabled");
        }
        ChronicleMapBuilder<Long, byte[]> builder = ChronicleMapBuilder
                .of(Long.class, byte[].class)
                .name("tailcache-sizing")
                .entries(ENTRIES_TARGET)
                .maxBloatFactor(MAX_BLOAT_FACTOR)
                .allowSegmentTiering(true)
                .checksumEntries(persistedPath != null)
                .putReturnsNull(true);
        byte[] configuredSample = new byte[estimate.configuredSampleBytes(actualPayloadBytes)];
        if (estimate == Estimate.CONSTANT) {
            builder.constantValueSizeBySample(configuredSample);
        } else {
            // averageValue() serializes the sample, including the byte[] length encoding.
            // Ratios are nominal payload lengths, not exact serialized byte counts.
            builder.averageValue(configuredSample);
        }
        return persistedPath == null ? builder.create() : builder.createPersistedTo(persistedPath.toFile());
    }

    static String policy(Estimate estimate, int actualPayloadBytes, boolean persisted) {
        return "entries=" + ENTRIES_TARGET
                + ",configuredSamplePayloadBytes=" + estimate.configuredSampleBytes(actualPayloadBytes)
                + ",actualPayloadBytes=" + actualPayloadBytes
                + ",valueSizing=" + (estimate == Estimate.CONSTANT ? "constant" : "average-sample")
                + ",maxBloatFactor=" + MAX_BLOAT_FACTOR
                + ",allowSegmentTiering=true,checksumEntries=" + persisted
                + ",putReturnsNull=true,persisted=" + persisted;
    }
}

package io.github.enixes.tailcache.cache;

import net.openhft.chronicle.map.ChronicleMap;
import net.openhft.chronicle.map.ChronicleMapBuilder;

import java.util.Objects;

/**
 * Chronicle Map adapter used for TailCache's off-heap backend.
 *
 * <p>The Java map object itself is an on-heap view, while Chronicle Map stores entry data in its
 * off-heap data store. The adapter owns that map instance and therefore must close it at the end
 * of each benchmark trial.</p>
 */
public final class ChronicleMapCacheAdapter implements CacheAdapter {

    private static final double MAX_BLOAT_FACTOR = 1.0d;
    private static final boolean ALLOW_SEGMENT_TIERING = true;
    private static final boolean PUT_RETURNS_NULL = true;

    private final ChronicleMap<Long, byte[]> map;
    private final long configuredEntries;
    private final int valueSizeBytes;

    public ChronicleMapCacheAdapter(CacheConfig config) {
        Objects.requireNonNull(config, "config");
        this.configuredEntries = config.maximumEntries();
        this.valueSizeBytes = config.valueSizeBytes();

        byte[] valueSizeSample = new byte[valueSizeBytes];
        this.map = ChronicleMapBuilder
                .of(Long.class, byte[].class)
                .name("tailcache")
                .entries(configuredEntries)
                .constantValueSizeBySample(valueSizeSample)
                .maxBloatFactor(MAX_BLOAT_FACTOR)
                .allowSegmentTiering(ALLOW_SEGMENT_TIERING)
                .putReturnsNull(PUT_RETURNS_NULL)
                .create();
    }

    @Override
    public String name() {
        return "chronicle-map";
    }

    @Override
    public String configurationSummary() {
        return "entries=" + configuredEntries
                + ",valueSizeBytes=" + valueSizeBytes
                + ",valueSizing=constant"
                + ",maxBloatFactor=" + MAX_BLOAT_FACTOR
                + ",allowSegmentTiering=" + ALLOW_SEGMENT_TIERING
                + ",putReturnsNull=" + PUT_RETURNS_NULL
                + ",entryStorage=off-heap"
                + ",persisted=false";
    }

    @Override
    public byte[] get(Long key) {
        return map.get(key);
    }

    @Override
    public void put(Long key, byte[] value) {
        map.put(key, Objects.requireNonNull(value, "value"));
    }

    @Override
    public long size() {
        return map.longSize();
    }

    @Override
    public void clear() {
        map.clear();
    }

    @Override
    public void close() {
        map.close();
    }
}

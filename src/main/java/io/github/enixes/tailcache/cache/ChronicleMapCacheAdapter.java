package io.github.enixes.tailcache.cache;

import net.openhft.chronicle.map.ChronicleMap;
import net.openhft.chronicle.map.ChronicleMapBuilder;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Path;
import java.util.Objects;

/**
 * Chronicle Map adapter used for TailCache's off-heap backend.
 *
 * <p>The Java map object itself is an on-heap view, while Chronicle Map stores entry data in its
 * off-heap data store. In persisted mode that store is file-backed/memory-mapped. The adapter owns
 * the map instance and must close it at the end of each benchmark trial; benchmark code separately
 * owns and deletes any temporary persisted file.</p>
 */
public final class ChronicleMapCacheAdapter implements CacheAdapter {

    private static final double MAX_BLOAT_FACTOR = 1.0d;
    private static final boolean ALLOW_SEGMENT_TIERING = true;
    private static final boolean PUT_RETURNS_NULL = true;

    private final ChronicleMap<Long, byte[]> map;
    private final long configuredEntries;
    private final int valueSizeBytes;
    private final ChronicleStorageMode storageMode;
    private final boolean entryChecksums;

    public ChronicleMapCacheAdapter(CacheConfig config) {
        this(config, ChronicleStorageMode.IN_MEMORY, null);
    }

    public ChronicleMapCacheAdapter(
            CacheConfig config,
            ChronicleStorageMode storageMode,
            Path persistedPath
    ) {
        Objects.requireNonNull(config, "config");
        this.storageMode = Objects.requireNonNull(storageMode, "storageMode");
        this.configuredEntries = config.maximumEntries();
        this.valueSizeBytes = config.valueSizeBytes();
        this.entryChecksums = storageMode == ChronicleStorageMode.PERSISTED;

        if (storageMode == ChronicleStorageMode.PERSISTED) {
            Objects.requireNonNull(persistedPath, "persistedPath");
        } else if (persistedPath != null) {
            throw new IllegalArgumentException("persistedPath is only valid for PERSISTED storage mode");
        }

        byte[] valueSizeSample = new byte[valueSizeBytes];
        ChronicleMapBuilder<Long, byte[]> builder = ChronicleMapBuilder
                .of(Long.class, byte[].class)
                .name("tailcache")
                .entries(configuredEntries)
                .constantValueSizeBySample(valueSizeSample)
                .maxBloatFactor(MAX_BLOAT_FACTOR)
                .allowSegmentTiering(ALLOW_SEGMENT_TIERING)
                .checksumEntries(entryChecksums)
                .putReturnsNull(PUT_RETURNS_NULL);

        this.map = createMap(builder, storageMode, persistedPath);
    }

    private static ChronicleMap<Long, byte[]> createMap(
            ChronicleMapBuilder<Long, byte[]> builder,
            ChronicleStorageMode storageMode,
            Path persistedPath
    ) {
        if (storageMode == ChronicleStorageMode.IN_MEMORY) {
            return builder.create();
        }

        try {
            return builder.createPersistedTo(persistedPath.toFile());
        } catch (IOException exception) {
            throw new UncheckedIOException("Failed to create persisted Chronicle Map at " + persistedPath, exception);
        }
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
                + ",entryChecksums=" + entryChecksums
                + ",putReturnsNull=" + PUT_RETURNS_NULL
                + ",entryStorage=off-heap"
                + ",storageMode=" + storageMode
                + ",persisted=" + (storageMode == ChronicleStorageMode.PERSISTED);
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

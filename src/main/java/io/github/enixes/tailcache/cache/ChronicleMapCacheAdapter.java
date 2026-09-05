package io.github.enixes.tailcache.cache;

import net.openhft.chronicle.map.ChronicleMap;
import net.openhft.chronicle.map.ChronicleMapBuilder;

import java.util.Objects;

public final class ChronicleMapCacheAdapter implements CacheAdapter {

    private final ChronicleMap<Long, byte[]> map;

    public ChronicleMapCacheAdapter(CacheConfig config) {
        Objects.requireNonNull(config, "config");
        this.map = ChronicleMapBuilder
                .of(Long.class, byte[].class)
                .name("tailcache")
                .entries(config.maximumEntries())
                .averageValueSize(config.averageValueSizeBytes())
                .create();
    }

    @Override
    public String name() {
        return "chronicle-map";
    }

    @Override
    public byte[] get(long key) {
        return map.get(key);
    }

    @Override
    public void put(long key, byte[] value) {
        map.put(key, Objects.requireNonNull(value, "value"));
    }

    @Override
    public long size() {
        return map.size();
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

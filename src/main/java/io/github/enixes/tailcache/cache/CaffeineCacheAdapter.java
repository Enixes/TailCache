package io.github.enixes.tailcache.cache;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;

import java.util.Objects;

public final class CaffeineCacheAdapter implements CacheAdapter {

    private final Cache<Long, byte[]> cache;

    public CaffeineCacheAdapter(CacheConfig config) {
        Objects.requireNonNull(config, "config");
        this.cache = Caffeine.newBuilder()
                .maximumSize(config.maximumEntries())
                .build();
    }

    @Override
    public String name() {
        return "caffeine";
    }

    @Override
    public byte[] get(long key) {
        return cache.getIfPresent(key);
    }

    @Override
    public void put(long key, byte[] value) {
        cache.put(key, Objects.requireNonNull(value, "value"));
    }

    @Override
    public long size() {
        cache.cleanUp();
        return cache.estimatedSize();
    }

    @Override
    public void clear() {
        cache.invalidateAll();
        cache.cleanUp();
    }

    @Override
    public void close() {
        clear();
    }
}

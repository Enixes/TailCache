package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.cache.CacheAdapter;
import io.github.enixes.tailcache.cache.CacheConfig;
import io.github.enixes.tailcache.cache.CaffeineCacheAdapter;
import io.github.enixes.tailcache.cache.ChronicleMapCacheAdapter;
import io.github.enixes.tailcache.cache.ChronicleStorageMode;

import java.nio.file.Path;

/**
 * Primary TailCache benchmark modes. Persisted Chronicle is a single-JVM file-backed mode here;
 * multi-JVM sharing is intentionally a separate experiment.
 */
public enum BenchmarkBackendMode {
    CAFFEINE {
        @Override
        CacheAdapter create(CacheConfig config, Path persistedPath) {
            requireNoPersistedPath(persistedPath);
            return new CaffeineCacheAdapter(config);
        }
    },
    CHRONICLE_IN_MEMORY {
        @Override
        CacheAdapter create(CacheConfig config, Path persistedPath) {
            requireNoPersistedPath(persistedPath);
            return new ChronicleMapCacheAdapter(config, ChronicleStorageMode.IN_MEMORY, null);
        }
    },
    CHRONICLE_PERSISTED {
        @Override
        CacheAdapter create(CacheConfig config, Path persistedPath) {
            if (persistedPath == null) {
                throw new IllegalArgumentException("CHRONICLE_PERSISTED requires a persisted path");
            }
            return new ChronicleMapCacheAdapter(config, ChronicleStorageMode.PERSISTED, persistedPath);
        }
    };

    abstract CacheAdapter create(CacheConfig config, Path persistedPath);

    public boolean isPersisted() {
        return this == CHRONICLE_PERSISTED;
    }

    private static void requireNoPersistedPath(Path persistedPath) {
        if (persistedPath != null) {
            throw new IllegalArgumentException("persisted path is only valid for CHRONICLE_PERSISTED");
        }
    }
}

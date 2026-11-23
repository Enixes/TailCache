package io.github.enixes.tailcache.workload;

import io.github.enixes.tailcache.cache.CacheAdapter;
import io.github.enixes.tailcache.cache.CacheConfig;
import io.github.enixes.tailcache.cache.CaffeineCacheAdapter;
import io.github.enixes.tailcache.cache.ChronicleMapCacheAdapter;

/** Task 12 primary comparison excludes persisted storage. */
public enum CrossoverBackend {
    CAFFEINE, CHRONICLE_IN_MEMORY, CAFFEINE_BOUNDED_DIRECT, CAFFEINE_UNBOUNDED;

    public CacheAdapter create(CrossoverConfig config) {
        return switch (this) {
            case CAFFEINE -> new CaffeineCacheAdapter(
                    new CacheConfig(config.caffeineMaximumSize(), config.payloadBytes()));
            case CAFFEINE_BOUNDED_DIRECT -> new CaffeineCacheAdapter(
                    new CacheConfig(config.caffeineMaximumSize(), config.payloadBytes()), CaffeineCacheAdapter.Policy.BOUNDED_DIRECT);
            case CAFFEINE_UNBOUNDED -> new CaffeineCacheAdapter(
                    new CacheConfig(config.caffeineMaximumSize(), config.payloadBytes()), CaffeineCacheAdapter.Policy.UNBOUNDED);
            case CHRONICLE_IN_MEMORY -> new ChronicleMapCacheAdapter(
                    new CacheConfig(config.chronicleEntriesTarget(), config.payloadBytes()));
        };
    }
}

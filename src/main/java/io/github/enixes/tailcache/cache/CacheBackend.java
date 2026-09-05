package io.github.enixes.tailcache.cache;

public enum CacheBackend {
    CAFFEINE {
        @Override
        public CacheAdapter create(CacheConfig config) {
            return new CaffeineCacheAdapter(config);
        }
    },
    CHRONICLE_MAP {
        @Override
        public CacheAdapter create(CacheConfig config) {
            return new ChronicleMapCacheAdapter(config);
        }
    };

    public abstract CacheAdapter create(CacheConfig config);
}

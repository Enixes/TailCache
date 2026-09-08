package io.github.enixes.tailcache.cache;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class ChronicleMapCacheAdapterTest {

    @Test
    void basicContract() {
        try (CacheAdapter cache = new ChronicleMapCacheAdapter(new CacheConfig(100, 32))) {
            assertEquals("chronicle-map", cache.name());
            assertEquals("entries=100,averageValueSizeBytes=32", cache.configurationSummary());
            assertNull(cache.get(1L));

            byte[] value = {1, 2, 3};
            cache.put(1L, value);

            assertArrayEquals(value, cache.get(1L));
            assertEquals(1, cache.size());

            cache.clear();
            assertNull(cache.get(1L));
            assertEquals(0, cache.size());
        }
    }
}

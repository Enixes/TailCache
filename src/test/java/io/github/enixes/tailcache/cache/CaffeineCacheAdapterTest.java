package io.github.enixes.tailcache.cache;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CaffeineCacheAdapterTest {

    @Test
    void hitMissOverwriteAndClearContract() {
        try (CacheAdapter cache = new CaffeineCacheAdapter(new CacheConfig(100, 32))) {
            assertEquals("caffeine", cache.name());
            assertEquals("maximumSize=100", cache.configurationSummary());
            assertNull(cache.get(1L));

            byte[] firstValue = {1, 2, 3};
            cache.put(1L, firstValue);

            assertSame(firstValue, cache.get(1L));
            assertEquals(1, cache.size());

            byte[] replacement = {4, 5, 6};
            cache.put(1L, replacement);

            assertSame(replacement, cache.get(1L));
            assertEquals(1, cache.size());

            cache.clear();
            assertNull(cache.get(1L));
            assertEquals(0, cache.size());
        }
    }

    @Test
    void maximumSizeIsEnforcedAfterMaintenance() {
        try (CacheAdapter cache = new CaffeineCacheAdapter(new CacheConfig(2, 32))) {
            cache.put(1L, new byte[] {1});
            cache.put(2L, new byte[] {2});
            cache.put(3L, new byte[] {3});

            assertTrue(cache.size() <= 2, "Caffeine must respect the configured maximumSize");
        }
    }
}

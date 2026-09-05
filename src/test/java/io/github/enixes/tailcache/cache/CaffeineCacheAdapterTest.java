package io.github.enixes.tailcache.cache;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class CaffeineCacheAdapterTest {

    @Test
    void basicContract() {
        try (CacheAdapter cache = new CaffeineCacheAdapter(new CacheConfig(100, 32))) {
            assertNull(cache.get(1));

            byte[] value = {1, 2, 3};
            cache.put(1, value);

            assertArrayEquals(value, cache.get(1));
            assertEquals(1, cache.size());

            cache.clear();
            assertNull(cache.get(1));
            assertEquals(0, cache.size());
        }
    }
}

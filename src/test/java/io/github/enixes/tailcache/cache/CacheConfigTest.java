package io.github.enixes.tailcache.cache;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;

class CacheConfigTest {

    @Test
    void rejectsNonPositiveCapacity() {
        assertThrows(IllegalArgumentException.class, () -> new CacheConfig(0, 128));
    }

    @Test
    void rejectsNonPositiveAverageValueSize() {
        assertThrows(IllegalArgumentException.class, () -> new CacheConfig(100, 0));
    }
}

package io.github.enixes.tailcache.cache;

import net.openhft.chronicle.hash.ChronicleHashClosedException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ChronicleMapCacheAdapterTest {

    @Test
    void hitMissOverwriteAndClearContract() {
        try (CacheAdapter cache = new ChronicleMapCacheAdapter(new CacheConfig(100, 32))) {
            assertEquals("chronicle-map", cache.name());
            assertEquals(
                    "entries=100,averageValueSizeBytes=32,maxBloatFactor=1.0,putReturnsNull=true,storage=off-heap",
                    cache.configurationSummary()
            );
            assertNull(cache.get(1L));

            byte[] firstValue = {1, 2, 3};
            cache.put(1L, firstValue);

            assertArrayEquals(firstValue, cache.get(1L));
            assertEquals(1, cache.size());

            byte[] replacement = {4, 5, 6};
            cache.put(1L, replacement);

            assertArrayEquals(replacement, cache.get(1L));
            assertEquals(1, cache.size());

            cache.clear();
            assertNull(cache.get(1L));
            assertEquals(0, cache.size());
        }
    }

    @Test
    void closeIsIdempotentAndRejectsFurtherAccess() {
        ChronicleMapCacheAdapter cache = new ChronicleMapCacheAdapter(new CacheConfig(16, 32));
        cache.put(1L, new byte[] {1, 2, 3});

        cache.close();
        assertThrows(ChronicleHashClosedException.class, () -> cache.get(1L));

        // Chronicle Map documents repeated close calls as safe.
        cache.close();
    }
}

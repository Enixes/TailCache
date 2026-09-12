package io.github.enixes.tailcache.cache;

import net.openhft.chronicle.hash.ChronicleHashClosedException;
import org.junit.jupiter.api.Test;

import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ChronicleMapCacheAdapterTest {

    private static final int VALUE_SIZE = 32;

    @Test
    void hitMissOverwriteAndClearContract() {
        try (CacheAdapter cache = new ChronicleMapCacheAdapter(new CacheConfig(100, VALUE_SIZE))) {
            assertEquals("chronicle-map", cache.name());
            assertEquals(
                    "entries=100,valueSizeBytes=32,valueSizing=constant,maxBloatFactor=1.0,allowSegmentTiering=true,putReturnsNull=true,entryStorage=off-heap,persisted=false",
                    cache.configurationSummary()
            );
            assertNull(cache.get(1L));

            byte[] firstValue = new byte[VALUE_SIZE];
            Arrays.fill(firstValue, (byte) 1);
            cache.put(1L, firstValue);

            assertArrayEquals(firstValue, cache.get(1L));
            assertEquals(1, cache.size());

            byte[] replacement = new byte[VALUE_SIZE];
            Arrays.fill(replacement, (byte) 2);
            cache.put(1L, replacement);

            assertArrayEquals(replacement, cache.get(1L));
            assertEquals(1, cache.size());

            cache.clear();
            assertNull(cache.get(1L));
            assertEquals(0, cache.size());
        }
    }

    @Test
    void rejectsValueWhoseSizeDoesNotMatchConfiguredConstantSize() {
        try (CacheAdapter cache = new ChronicleMapCacheAdapter(new CacheConfig(16, VALUE_SIZE))) {
            assertThrows(IllegalArgumentException.class, () -> cache.put(1L, new byte[VALUE_SIZE - 1]));
        }
    }

    @Test
    void closeIsIdempotentAndRejectsFurtherAccess() {
        ChronicleMapCacheAdapter cache = new ChronicleMapCacheAdapter(new CacheConfig(16, VALUE_SIZE));
        cache.put(1L, new byte[VALUE_SIZE]);

        cache.close();
        assertThrows(ChronicleHashClosedException.class, () -> cache.get(1L));

        // Chronicle Map documents repeated close calls as safe.
        cache.close();
    }
}

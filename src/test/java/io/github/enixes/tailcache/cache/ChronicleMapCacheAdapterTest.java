package io.github.enixes.tailcache.cache;

import net.openhft.chronicle.hash.ChronicleHashClosedException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ChronicleMapCacheAdapterTest {

    private static final int VALUE_SIZE = 32;

    @Test
    void hitMissOverwriteAndClearContract() {
        try (CacheAdapter cache = new ChronicleMapCacheAdapter(new CacheConfig(100, VALUE_SIZE))) {
            assertEquals("chronicle-map", cache.name());
            assertEquals(
                    "entries=100,valueSizeBytes=32,valueSizing=constant,maxBloatFactor=1.0,allowSegmentTiering=true,entryChecksums=false,putReturnsNull=true,entryStorage=off-heap,storageMode=IN_MEMORY,persisted=false",
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
    void persistedModeSurvivesCloseAndReopen(@TempDir Path tempDir) {
        Path mapFile = tempDir.resolve("tailcache-test.dat");
        CacheConfig config = new CacheConfig(16, VALUE_SIZE);
        byte[] value = new byte[VALUE_SIZE];
        Arrays.fill(value, (byte) 7);

        try (CacheAdapter cache = new ChronicleMapCacheAdapter(
                config,
                ChronicleStorageMode.PERSISTED,
                mapFile
        )) {
            cache.put(1L, value);

            assertArrayEquals(value, cache.get(1L));
            assertEquals(1, cache.size());
            assertTrue(cache.configurationSummary().contains("entryChecksums=true"));
            assertTrue(cache.configurationSummary().contains("storageMode=PERSISTED,persisted=true"));
        }

        assertTrue(Files.exists(mapFile), "adapter close should not silently delete persisted data");

        try (CacheAdapter reopened = new ChronicleMapCacheAdapter(
                config,
                ChronicleStorageMode.PERSISTED,
                mapFile
        )) {
            assertArrayEquals(value, reopened.get(1L));
            assertEquals(1, reopened.size());
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

package io.github.enixes.tailcache.cache;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Reproduces https://github.com/OpenHFT/Chronicle-Map/issues/533 with TailCache's adapter. */
class ChronicleMapCapacityReproTest {

    @Test
    void persistedMapExhaustsExtraTiersAfterExceedingEntriesTarget(@TempDir Path tempDir) {
        long configuredEntries = 16;
        byte[] value = new byte[32];

        try (CacheAdapter cache = new ChronicleMapCacheAdapter(
                new CacheConfig(configuredEntries, value.length),
                ChronicleStorageMode.PERSISTED,
                tempDir.resolve("capacity-repro.dat")
        )) {
            IllegalStateException failure = assertThrows(IllegalStateException.class, () -> {
                for (long key = 0; key < 1_000; key++) {
                    cache.put(key, value);
                }
            });

            assertTrue(cache.size() > configuredEntries,
                    "the map should accept some entries beyond its target before exhausting tiers");
            assertTrue(failure.getMessage().contains(
                    "Attempt to allocate #2 extra segment tier, 1 is maximum."));
        }
    }
}

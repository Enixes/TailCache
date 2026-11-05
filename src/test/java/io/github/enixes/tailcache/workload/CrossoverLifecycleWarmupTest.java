package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CrossoverLifecycleWarmupTest {
    @Test void absentPreparationKeepsLegacyBehaviorAndUnknownControlFailsBeforeWork() {
        String old = System.getProperty("tailcache12.lifecycleWarmupVersion");
        System.setProperty("chronicle.analytics.disable", "true");
        var config = new CrossoverConfig(16, 256, 24301, 0, 4096, 0, 128);
        try {
            System.setProperty("tailcache12.lifecycleWarmupVersion", "none");
            assertEquals(0, CrossoverLifecycleWarmup.prepare(CrossoverBackend.CAFFEINE, config).operations());
            System.setProperty("tailcache12.lifecycleWarmupVersion", "unknown");
            assertThrows(IllegalArgumentException.class, () ->
                    CrossoverLifecycleWarmup.prepare(CrossoverBackend.CAFFEINE, config));
        } finally {
            if (old == null) System.clearProperty("tailcache12.lifecycleWarmupVersion");
            else System.setProperty("tailcache12.lifecycleWarmupVersion", old);
        }
    }

    @Test void disposableMaintenanceUsesTheSameOperationsAndLeavesOnlyPrimitiveEvidence() {
        System.setProperty("chronicle.analytics.disable", "true");
        var config = new CrossoverConfig(64, 256, 24301, 8192, 4096, 0, 128);
        var caffeine = CrossoverLifecycleWarmup.prepare(CrossoverBackend.CAFFEINE, config, 8);
        var chronicle = CrossoverLifecycleWarmup.prepare(CrossoverBackend.CHRONICLE_IN_MEMORY, config, 8);
        assertEquals(3L * 8 * 128, caffeine.operations());
        assertEquals(caffeine.operations(), chronicle.operations());
        assertEquals(caffeine.writes(), chronicle.writes());
        assertEquals(caffeine.checksum(), chronicle.checksum());
        assertTrue(caffeine.writes() > 0);
        for (var component : CrossoverLifecycleWarmup.Evidence.class.getRecordComponents()) {
            assertTrue(component.getType().isPrimitive());
        }
        try (var fresh = new CrossoverWorkload(CrossoverBackend.CAFFEINE, config)) {
            assertEquals(0, fresh.operations());
            assertEquals(0, fresh.writes());
            assertEquals(64, fresh.size());
            fresh.verifyContents();
        }
        assertThrows(IllegalArgumentException.class, () ->
                CrossoverLifecycleWarmup.prepare(CrossoverBackend.CAFFEINE, config, -1));
        assertThrows(IllegalArgumentException.class, () ->
                CrossoverLifecycleWarmup.prepare(CrossoverBackend.CAFFEINE, config, 20_001));
    }
}

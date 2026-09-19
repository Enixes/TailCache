package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DeterministicWorkloadGeneratorTest {

    private final DeterministicWorkloadGenerator generator = new DeterministicWorkloadGenerator();

    @Test
    void sameSpecProducesSameTrace() {
        WorkloadSpec spec = WorkloadSpec.zipfian(10_000, 1_000, 0.95, 42L);

        assertEquals(generator.generate(spec), generator.generate(spec));
    }

    @Test
    void changingSeedChangesTrace() {
        WorkloadSpec first = WorkloadSpec.uniform(1_000, 100, 1.0, 1L);
        WorkloadSpec second = WorkloadSpec.uniform(1_000, 100, 1.0, 2L);

        assertNotEquals(generator.generate(first), generator.generate(second));
    }

    @Test
    void exactReadWriteMixIsPreserved() {
        WorkloadTrace trace = generator.generate(WorkloadSpec.uniform(10_000, 100, 0.95, 11L));

        int reads = 0;
        for (int i = 0; i < trace.size(); i++) {
            if (trace.isReadAt(i)) {
                reads++;
            }
        }

        assertEquals(9_500, reads);
    }

    @Test
    void changingReadRatioDoesNotChangeKeySequence() {
        WorkloadTrace mostlyReads = generator.generate(WorkloadSpec.zipfian(10_000, 1_000, 0.95, 19L));
        WorkloadTrace mixed = generator.generate(WorkloadSpec.zipfian(10_000, 1_000, 0.70, 19L));

        for (int i = 0; i < mostlyReads.size(); i++) {
            assertEquals(mostlyReads.keyAt(i), mixed.keyAt(i));
        }
        assertNotEquals(mostlyReads, mixed);
    }

    @Test
    void zipfianConcentratesAccessesTowardLowRanks() {
        WorkloadSpec spec = WorkloadSpec.zipfian(100_000, 1_000, 1.0, 7L);
        WorkloadTrace trace = generator.generate(spec);

        long topTenPercent = 0;
        for (int i = 0; i < trace.size(); i++) {
            if (trace.keyAt(i) < 100) {
                topTenPercent++;
            }
        }

        double observed = topTenPercent / (double) trace.size();
        assertTrue(observed > 0.65 && observed < 0.72, "observed top-10% share=" + observed);
    }

    @Test
    void hotspotConcentratesMostAccessesInHotSet() {
        WorkloadSpec spec = WorkloadSpec.hotspot(100_000, 1_000, 1.0, 7L, 0.2, 0.8);
        WorkloadTrace trace = generator.generate(spec);

        long hot = 0;
        for (int i = 0; i < trace.size(); i++) {
            if (trace.keyAt(i) < 200) {
                hot++;
            }
        }

        double observed = hot / (double) trace.size();
        assertTrue(observed > 0.78 && observed < 0.82, "observed hot-set share=" + observed);
    }
}

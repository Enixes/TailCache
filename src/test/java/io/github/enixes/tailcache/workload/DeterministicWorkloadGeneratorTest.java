package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DeterministicWorkloadGeneratorTest {

    private final DeterministicWorkloadGenerator generator = new DeterministicWorkloadGenerator();

    @Test
    void sameSpecProducesSameTrace() {
        WorkloadSpec spec = WorkloadSpec.hotspot(10_000, 1_000, 0.9, 42L, 0.2, 0.8);

        assertEquals(generator.generate(spec), generator.generate(spec));
    }

    @Test
    void changingSeedChangesTrace() {
        WorkloadSpec first = WorkloadSpec.uniform(1_000, 100, 1.0, 1L);
        WorkloadSpec second = WorkloadSpec.uniform(1_000, 100, 1.0, 2L);

        assertNotEquals(generator.generate(first), generator.generate(second));
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

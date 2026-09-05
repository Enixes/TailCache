package io.github.enixes.tailcache.workload;

import java.util.Objects;
import java.util.SplittableRandom;

/**
 * Generates a complete trace before benchmarking so PRNG cost is outside measured cache operations.
 */
public final class DeterministicWorkloadGenerator {

    public WorkloadTrace generate(WorkloadSpec spec) {
        Objects.requireNonNull(spec, "spec");
        SplittableRandom random = new SplittableRandom(spec.seed());

        long[] keys = new long[spec.operationCount()];
        boolean[] reads = new boolean[spec.operationCount()];

        int hotSetSize = Math.max(1, (int) Math.round(spec.keySpace() * spec.hotSetFraction()));
        hotSetSize = Math.min(hotSetSize, spec.keySpace());

        for (int i = 0; i < spec.operationCount(); i++) {
            reads[i] = random.nextDouble() < spec.readRatio();
            keys[i] = switch (spec.accessPattern()) {
                case UNIFORM -> random.nextInt(spec.keySpace());
                case HOTSPOT -> nextHotspotKey(random, spec, hotSetSize);
            };
        }

        return new WorkloadTrace(keys, reads);
    }

    private static long nextHotspotKey(SplittableRandom random, WorkloadSpec spec, int hotSetSize) {
        if (hotSetSize == spec.keySpace() || random.nextDouble() < spec.hotSetAccessProbability()) {
            return random.nextInt(hotSetSize);
        }
        return hotSetSize + random.nextInt(spec.keySpace() - hotSetSize);
    }
}

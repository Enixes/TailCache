package io.github.enixes.tailcache.workload;

import java.util.Objects;

public record WorkloadSpec(
        int operationCount,
        int keySpace,
        double readRatio,
        AccessPattern accessPattern,
        long seed,
        double hotSetFraction,
        double hotSetAccessProbability
) {

    public WorkloadSpec {
        if (operationCount <= 0) {
            throw new IllegalArgumentException("operationCount must be > 0");
        }
        if (keySpace <= 0) {
            throw new IllegalArgumentException("keySpace must be > 0");
        }
        requireProbability(readRatio, "readRatio");
        Objects.requireNonNull(accessPattern, "accessPattern");
        if (!(hotSetFraction > 0.0 && hotSetFraction <= 1.0)) {
            throw new IllegalArgumentException("hotSetFraction must be in (0, 1]");
        }
        requireProbability(hotSetAccessProbability, "hotSetAccessProbability");
    }

    public static WorkloadSpec uniform(int operationCount, int keySpace, double readRatio, long seed) {
        return new WorkloadSpec(
                operationCount, keySpace, readRatio, AccessPattern.UNIFORM, seed, 0.2, 0.8
        );
    }

    public static WorkloadSpec hotspot(
            int operationCount,
            int keySpace,
            double readRatio,
            long seed,
            double hotSetFraction,
            double hotSetAccessProbability
    ) {
        return new WorkloadSpec(
                operationCount, keySpace, readRatio, AccessPattern.HOTSPOT, seed,
                hotSetFraction, hotSetAccessProbability
        );
    }

    private static void requireProbability(double value, String name) {
        if (value < 0.0 || value > 1.0 || Double.isNaN(value)) {
            throw new IllegalArgumentException(name + " must be in [0, 1]");
        }
    }
}

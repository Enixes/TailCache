package io.github.enixes.tailcache.workload;

import java.util.Objects;

public record WorkloadSpec(
        int operationCount,
        int keySpace,
        double readRatio,
        AccessPattern accessPattern,
        long seed,
        double hotSetFraction,
        double hotSetAccessProbability,
        double zipfExponent
) {

    /**
     * Initial Zipfian skew used by TailCache. This matches YCSB's long-standing default theta.
     */
    public static final double DEFAULT_ZIPF_EXPONENT = 0.99d;

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
        if (!(zipfExponent > 0.0) || !Double.isFinite(zipfExponent)) {
            throw new IllegalArgumentException("zipfExponent must be finite and > 0");
        }
    }

    public static WorkloadSpec uniform(int operationCount, int keySpace, double readRatio, long seed) {
        return new WorkloadSpec(
                operationCount,
                keySpace,
                readRatio,
                AccessPattern.UNIFORM,
                seed,
                0.2,
                0.8,
                DEFAULT_ZIPF_EXPONENT
        );
    }

    public static WorkloadSpec zipfian(int operationCount, int keySpace, double readRatio, long seed) {
        return zipfian(operationCount, keySpace, readRatio, seed, DEFAULT_ZIPF_EXPONENT);
    }

    public static WorkloadSpec zipfian(
            int operationCount,
            int keySpace,
            double readRatio,
            long seed,
            double zipfExponent
    ) {
        return new WorkloadSpec(
                operationCount,
                keySpace,
                readRatio,
                AccessPattern.ZIPFIAN,
                seed,
                0.2,
                0.8,
                zipfExponent
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
                operationCount,
                keySpace,
                readRatio,
                AccessPattern.HOTSPOT,
                seed,
                hotSetFraction,
                hotSetAccessProbability,
                DEFAULT_ZIPF_EXPONENT
        );
    }

    private static void requireProbability(double value, String name) {
        if (value < 0.0 || value > 1.0 || Double.isNaN(value)) {
            throw new IllegalArgumentException(name + " must be in [0, 1]");
        }
    }
}

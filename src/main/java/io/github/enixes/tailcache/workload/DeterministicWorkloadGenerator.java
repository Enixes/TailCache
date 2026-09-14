package io.github.enixes.tailcache.workload;

import java.util.Arrays;
import java.util.Objects;
import java.util.SplittableRandom;

/**
 * Generates a complete trace before benchmarking so PRNG and distribution-generation costs stay
 * outside measured cache operations.
 */
public final class DeterministicWorkloadGenerator {

    private static final long KEY_STREAM_SALT = 0x9E3779B97F4A7C15L;
    private static final long OPERATION_STREAM_SALT = 0xD1B54A32D192ED03L;

    public WorkloadTrace generate(WorkloadSpec spec) {
        Objects.requireNonNull(spec, "spec");

        // Keep key selection independent from the read/write mix. That lets two workload mixes use
        // the same key sequence when every other distribution parameter and seed is unchanged.
        SplittableRandom keyRandom = new SplittableRandom(spec.seed() ^ KEY_STREAM_SALT);
        SplittableRandom operationRandom = new SplittableRandom(spec.seed() ^ OPERATION_STREAM_SALT);

        long[] keys = new long[spec.operationCount()];
        boolean[] reads = exactReadWriteMix(spec.operationCount(), spec.readRatio(), operationRandom);

        int hotSetSize = Math.max(1, (int) Math.round(spec.keySpace() * spec.hotSetFraction()));
        hotSetSize = Math.min(hotSetSize, spec.keySpace());
        double[] zipfCdf = spec.accessPattern() == AccessPattern.ZIPFIAN
                ? buildZipfCdf(spec.keySpace(), spec.zipfExponent())
                : null;

        for (int i = 0; i < spec.operationCount(); i++) {
            keys[i] = switch (spec.accessPattern()) {
                case UNIFORM -> keyRandom.nextInt(spec.keySpace());
                case ZIPFIAN -> nextZipfianKey(keyRandom, zipfCdf);
                case HOTSPOT -> nextHotspotKey(keyRandom, spec, hotSetSize);
            };
        }

        return new WorkloadTrace(keys, reads);
    }

    private static boolean[] exactReadWriteMix(
            int operationCount,
            double readRatio,
            SplittableRandom random
    ) {
        boolean[] reads = new boolean[operationCount];
        int readCount = (int) Math.round(operationCount * readRatio);
        Arrays.fill(reads, 0, readCount, true);

        // Fisher-Yates shuffle gives an exact aggregate mix without introducing a periodic pattern.
        for (int i = reads.length - 1; i > 0; i--) {
            int j = random.nextInt(i + 1);
            boolean temporary = reads[i];
            reads[i] = reads[j];
            reads[j] = temporary;
        }
        return reads;
    }

    private static double[] buildZipfCdf(int keySpace, double exponent) {
        double normalization = 0.0;
        for (int rank = 1; rank <= keySpace; rank++) {
            normalization += 1.0 / Math.pow(rank, exponent);
        }

        double[] cdf = new double[keySpace];
        double cumulative = 0.0;
        for (int rank = 1; rank <= keySpace; rank++) {
            cumulative += (1.0 / Math.pow(rank, exponent)) / normalization;
            cdf[rank - 1] = cumulative;
        }
        cdf[cdf.length - 1] = 1.0;
        return cdf;
    }

    private static long nextZipfianKey(SplittableRandom random, double[] cdf) {
        double sample = random.nextDouble();
        int index = Arrays.binarySearch(cdf, sample);
        if (index < 0) {
            index = -index - 1;
        }
        return Math.min(index, cdf.length - 1);
    }

    private static long nextHotspotKey(SplittableRandom random, WorkloadSpec spec, int hotSetSize) {
        if (hotSetSize == spec.keySpace() || random.nextDouble() < spec.hotSetAccessProbability()) {
            return random.nextInt(hotSetSize);
        }
        return hotSetSize + random.nextInt(spec.keySpace() - hotSetSize);
    }
}

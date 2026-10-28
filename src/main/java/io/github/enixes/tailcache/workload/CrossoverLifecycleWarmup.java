package io.github.enixes.tailcache.workload;

/** Exercises startup/cleanup before either latency channel constructs its measured state. */
public final class CrossoverLifecycleWarmup {
    public static final int TRIALS = 3;
    private static volatile long consumed;

    private CrossoverLifecycleWarmup() { }

    public static void prepare(CrossoverBackend backend, CrossoverConfig config) {
        CrossoverConfig disposable = new CrossoverConfig(config.residentEntries(), config.payloadBytes(),
                config.seed(), 0, config.applicationObjectBytes(), 0, config.churnRingSlots());
        long checksum = 0;
        for (int trial = 0; trial < TRIALS; trial++) {
            try (CrossoverWorkload workload = new CrossoverWorkload(backend, disposable)) {
                checksum ^= workload.verifyContents();
            }
        }
        // Only a primitive survives; no disposable keys, arrays or cache are retained.
        consumed = checksum;
    }
}

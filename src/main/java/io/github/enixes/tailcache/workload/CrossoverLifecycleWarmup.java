package io.github.enixes.tailcache.workload;

/** Exercises startup/cleanup before either latency channel constructs its measured state. */
public final class CrossoverLifecycleWarmup {
    public static final int TRIALS = 3;
    public static final String VERSION = "lifecycle-maintenance-v1";
    public static final int MAINTENANCE_BATCHES = 20_000;
    public static final int BATCH_OPERATIONS = 128;
    private static volatile long consumed;

    private CrossoverLifecycleWarmup() { }

    public record Evidence(int trials, int maintenanceBatches, int batchOperations,
                           long operations, long writes, long checksum) { }

    public static String version() {
        return System.getProperty("tailcache12.lifecycleWarmupVersion", "none");
    }

    public static Evidence prepare(CrossoverBackend backend, CrossoverConfig config) {
        String version = version();
        if (!version.equals("none") && !version.equals(VERSION)) {
            throw new IllegalArgumentException("Unknown lifecycle preparation protocol");
        }
        return prepare(backend, config, version.equals(VERSION) ? MAINTENANCE_BATCHES : 0);
    }

    static Evidence prepare(CrossoverBackend backend, CrossoverConfig config, int batches) {
        if (batches < 0 || batches > MAINTENANCE_BATCHES) {
            throw new IllegalArgumentException("Invalid lifecycle preparation batch bound");
        }
        CrossoverConfig disposable = new CrossoverConfig(config.residentEntries(), config.payloadBytes(),
                config.seed(), 0, config.applicationObjectBytes(), 0, config.churnRingSlots());
        long checksum = 0, operations = 0, writes = 0;
        for (int trial = 0; trial < TRIALS; trial++) {
            try (CrossoverWorkload workload = new CrossoverWorkload(backend, disposable)) {
                for (int batch = 0; batch < batches; batch++) {
                    for (int operation = 0; operation < BATCH_OPERATIONS; operation++) {
                        checksum += workload.executeNext()[0];
                    }
                    if (workload.size() != disposable.residentEntries()) {
                        throw new IllegalStateException("Disposable lifecycle resident count changed");
                    }
                }
                checksum ^= workload.verifyContents();
                operations += workload.operations();
                writes += workload.writes();
            }
        }
        // Only a primitive survives; no disposable keys, arrays or cache are retained.
        consumed = checksum;
        return new Evidence(TRIALS, batches, BATCH_OPERATIONS, operations, writes, checksum);
    }
}

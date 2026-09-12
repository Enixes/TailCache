package io.github.enixes.tailcache.workload;

/**
 * Controlled mixed-operation ratios for the primary TailCache workload matrix.
 */
public enum ReadWriteMix {
    READ_95_WRITE_5(0.95),
    READ_70_WRITE_30(0.70);

    private final double readRatio;

    ReadWriteMix(double readRatio) {
        this.readRatio = readRatio;
    }

    public double readRatio() {
        return readRatio;
    }

    public double writeRatio() {
        return 1.0 - readRatio;
    }
}

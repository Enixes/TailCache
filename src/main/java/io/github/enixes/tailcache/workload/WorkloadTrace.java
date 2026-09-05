package io.github.enixes.tailcache.workload;

import java.util.Arrays;

/**
 * Immutable-by-API pre-generated operation trace.
 */
public final class WorkloadTrace {

    private final long[] keys;
    private final boolean[] reads;

    WorkloadTrace(long[] keys, boolean[] reads) {
        if (keys.length != reads.length) {
            throw new IllegalArgumentException("keys and reads must have equal length");
        }
        this.keys = keys;
        this.reads = reads;
    }

    public int size() {
        return keys.length;
    }

    public long keyAt(int index) {
        return keys[index];
    }

    public boolean isReadAt(int index) {
        return reads[index];
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof WorkloadTrace that)) {
            return false;
        }
        return Arrays.equals(keys, that.keys) && Arrays.equals(reads, that.reads);
    }

    @Override
    public int hashCode() {
        return 31 * Arrays.hashCode(keys) + Arrays.hashCode(reads);
    }
}

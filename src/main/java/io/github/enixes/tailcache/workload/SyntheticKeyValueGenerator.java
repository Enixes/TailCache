package io.github.enixes.tailcache.workload;

import java.util.Objects;

/**
 * Produces deterministic synthetic keys and values for benchmark setup.
 *
 * Generation happens before measurement so cache timings do not include PRNG,
 * allocation, or payload-construction cost.
 */
public final class SyntheticKeyValueGenerator {

    private static final long KEY_SEED = 0x243F6A8885A308D3L;
    private static final long KEY_STRIDE = 0x9E3779B97F4A7C15L;
    private static final long VALUE_SALT = 0xD1B54A32D192ED03L;

    /**
     * Returns a stable, unique key for every non-negative logical index used by
     * a benchmark dataset.
     */
    public long keyForIndex(int index) {
        if (index < 0) {
            throw new IllegalArgumentException("index must be >= 0");
        }
        return KEY_SEED + KEY_STRIDE * index;
    }

    public byte[] valueFor(long key, PayloadSize payloadSize) {
        Objects.requireNonNull(payloadSize, "payloadSize");
        return valueFor(key, payloadSize.bytes());
    }

    /**
     * Builds deterministic, non-zero synthetic bytes from the key.
     */
    public byte[] valueFor(long key, int sizeBytes) {
        if (sizeBytes <= 0) {
            throw new IllegalArgumentException("sizeBytes must be > 0");
        }

        byte[] value = new byte[sizeBytes];
        long state = key ^ VALUE_SALT;

        for (int i = 0; i < value.length; i++) {
            state ^= state << 13;
            state ^= state >>> 7;
            state ^= state << 17;
            value[i] = (byte) state;
        }

        return value;
    }
}

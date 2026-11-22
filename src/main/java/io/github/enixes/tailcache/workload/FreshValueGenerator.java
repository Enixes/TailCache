package io.github.enixes.tailcache.workload;

/** Versioned deterministic values. Each call returns a new, exclusively owned array. */
public final class FreshValueGenerator {
    public static final String VERSION = "xorshift-key-version-v1";

    public byte[] create(long key, long version, int bytes) {
        if (version < 0 || bytes < 16) throw new IllegalArgumentException("Invalid version or size");
        byte[] value = new byte[bytes];
        long state = key ^ Long.rotateLeft(version, 23) ^ 0xD1B54A32D192ED03L;
        for (int i = 0; i < bytes; i++) {
            state ^= state << 13;
            state ^= state >>> 7;
            state ^= state << 17;
            value[i] = (byte) state;
        }
        return value;
    }
}

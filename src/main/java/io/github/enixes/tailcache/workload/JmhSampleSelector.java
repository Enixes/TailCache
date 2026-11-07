package io.github.enixes.tailcache.workload;

/** Task12 generated-harness selector; work occurs outside the service boundary. */
public final class JmhSampleSelector {
    public static final String VERSION = "fixed-mixed-lcg-mask15-v1";

    private JmhSampleSelector() { }

    public static boolean select(int state, int mask) {
        // Austin Appleby's public-domain MurmurHash3 fmix32 finalizer:
        // https://github.com/aappleby/smhasher/blob/master/src/MurmurHash3.cpp
        // The LCG transition remains in JMH. Mixing avoids selecting its
        // deterministically periodic low bits; this is not an independence claim.
        state ^= state >>> 16;
        state *= 0x85ebca6b;
        state ^= state >>> 13;
        state *= 0xc2b2ae35;
        state ^= state >>> 16;
        return (state & mask) == 0;
    }
}

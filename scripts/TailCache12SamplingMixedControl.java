/** Offline control, same predeclared bounds; records all phases before failure. */
class TailCache12SamplingMixedControl {
    // Austin Appleby's public-domain MurmurHash3 fmix32, not a new PRNG claim.
    static int mixed(int value) {
        value ^= value >>> 16;
        value *= 0x85ebca6b;
        value ^= value >>> 13;
        value *= 0xc2b2ae35;
        return value ^ (value >>> 16);
    }

    public static void main(String[] args) {
        boolean passed = true;
        System.out.println("initialState,selector,phase,samples");
        for (int initial : new int[]{0, 1, -1}) {
            int[] stock = new int[512], candidate = new int[512];
            int rnd = initial;
            for (int operation = 0; operation < (1 << 24); operation++) {
                rnd = rnd * 1664525 + 1013904223;
                if ((rnd & 255) == 0) stock[operation % 512]++;
                if ((mixed(rnd) & 255) == 0) candidate[operation % 512]++;
            }
            int covered = 0, total = 0;
            for (int phase = 0; phase < 512; phase++) {
                System.out.printf("%d,stock,%d,%d%n", initial, phase, stock[phase]);
                System.out.printf("%d,mixed,%d,%d%n", initial, phase, candidate[phase]);
                if (stock[phase] > 0) covered++;
                passed &= candidate[phase] >= 64 && candidate[phase] <= 192;
                total += candidate[phase];
            }
            passed &= covered == 2 && Math.abs(total - 65536) <= 655.36;
        }
        if (!passed) throw new AssertionError("Predeclared selector-control bound failed");
    }
}

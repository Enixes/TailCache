import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;

/** Offline design diagnostic only: no cache, clocks, GC or latency endpoints. */
class TailCache12SamplingDesign {
    public static void main(String[] args) {
        System.out.println("seed,period,sampleStride,gcd,positionsPerFixedPhase,minWriteFraction,maxWriteFraction");
        for (long seed : new long[]{24301, 0xC0FFEE, 0xBADC0DE}) {
            for (int period : new int[]{40_000, 40_001}) {
                var trace = new DeterministicWorkloadGenerator().generate(
                        WorkloadSpec.uniform(period, 32768, .95, seed));
                for (int stride : new int[]{16, 32, 64, 128, 256}) {
                    int divisor = gcd(period, stride);
                    int[] visits = new int[period];
                    // The actual generated JMH LCG has full period modulo 2^k.
                    // Retain an explicit recurrence check, not just the gcd formula.
                    int rnd = 123456789;
                    int count = 0;
                    for (int i = 0; i < period * stride / divisor; i++) {
                        rnd = rnd * 1664525 + 1013904223;
                        if ((rnd & (stride - 1)) == 0) {
                            visits[i % period]++;
                            count++;
                        }
                    }
                    int covered = 0;
                    for (int n : visits) {
                        if (n > 0) covered++;
                        if (n > 1) throw new AssertionError("Repeated orbit position");
                    }
                    if (covered != period / divisor || count != covered) {
                        throw new AssertionError("LCG orbit disagrees with arithmetic");
                    }
                    double min = 1, max = 0;
                    for (int phase = 0; phase < divisor; phase++) {
                        int writes = 0, total = 0;
                        for (int p = phase; p < period; p += divisor) {
                            if (!trace.isReadAt(p)) writes++;
                            total++;
                        }
                        double fraction = (double) writes / total;
                        min = Math.min(min, fraction);
                        max = Math.max(max, fraction);
                    }
                    System.out.printf(java.util.Locale.ROOT, "%d,%d,%d,%d,%d,%.12f,%.12f%n",
                            seed, period, stride, divisor, covered, min, max);
                }
            }
        }
    }

    private static int gcd(int a, int b) {
        while (b != 0) { int remainder = a % b; a = b; b = remainder; }
        return a;
    }
}

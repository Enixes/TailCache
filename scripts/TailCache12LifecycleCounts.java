import io.github.enixes.tailcache.workload.CrossoverLifecycleWarmup;
import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;

/** Offline exact contract export from the matching generator, with no cache. */
class TailCache12LifecycleCounts {
    public static void main(String[] args) {
        int operations = CrossoverLifecycleWarmup.MAINTENANCE_BATCHES
                * CrossoverLifecycleWarmup.BATCH_OPERATIONS;
        System.out.println("seed,period,trials,operationsPerTrial,writes");
        for (long seed : new long[]{24301, 0xC0FFEE, 0xBADC0DE}) {
            for (int period : new int[]{40_000, 40_001}) {
                var trace = new DeterministicWorkloadGenerator().generate(
                        WorkloadSpec.uniform(period, 32768, .95, seed));
                int writes = 0;
                for (int i = 0; i < operations; i++) {
                    if (!trace.isReadAt(i % trace.size())) writes++;
                }
                System.out.printf("%d,%d,%d,%d,%d%n", seed, period,
                        CrossoverLifecycleWarmup.TRIALS, operations,
                        writes * CrossoverLifecycleWarmup.TRIALS);
            }
        }
    }
}

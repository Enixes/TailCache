import io.github.enixes.tailcache.workload.JmhSampleSelectionEvidence;
import java.nio.file.Files;
import java.nio.file.Path;

/** Setup-only loaded-class provenance; never constructs a cache or timed loop. */
class TailCache12SamplerProof {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("unique output root required");
        Path root = Path.of(args[0]);
        if (Files.exists(root)) throw new IllegalStateException("Retained proof exists");
        for (String method : new String[]{"mixedWorkload", "freshSupplyFloor"}) {
            Path directory = Files.createDirectories(root.resolve(method));
            Class<?> harness = Class.forName("io.github.enixes.tailcache.benchmark.jmh_generated.CrossoverBenchmark_" + method + "_jmhTest");
            JmhSampleSelectionEvidence.write(directory, harness);
        }
    }
}

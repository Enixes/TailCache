import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.HexFormat;

/** Setup-only deterministic fingerprint export; creates no cache or measured fork. */
class TailCache12Trace {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("resident count required");
        int residents = Integer.parseInt(args[0]);
        long[] seeds = {24301, 0xC0FFEE, 0xBADC0DE};
        System.out.println("{");
        for (int s = 0; s < seeds.length; s++) {
            var trace = new DeterministicWorkloadGenerator().generate(
                    WorkloadSpec.uniform(40_000, residents, .95, seeds[s]));
            var digest = MessageDigest.getInstance("SHA-256");
            var key = ByteBuffer.allocate(Long.BYTES);
            for (int i = 0; i < trace.size(); i++) {
                key.clear();
                key.putLong(trace.keyAt(i));
                digest.update(key.array());
                digest.update((byte) (trace.isReadAt(i) ? 1 : 0));
            }
            System.out.printf("  \"%d\": \"%s\"%s%n", seeds[s],
                    HexFormat.of().formatHex(digest.digest()), s+1 < seeds.length ? "," : "");
        }
        System.out.println("}");
    }
}

import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.*;

/** Offline trace inspection only: never constructs a cache or times operations. */
public final class TailCacheTraceReview {
    public static void main(String[] args) throws Exception {
        for (long seed : new long[]{24301, 24302, 24303}) {
            var trace = new DeterministicWorkloadGenerator().generate(
                    WorkloadSpec.uniform(40001, 32768, .95, seed));
            Set<Long> all = new HashSet<>(), reads = new HashSet<>(), writes = new HashSet<>();
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            ByteBuffer key = ByteBuffer.allocate(8);
            int readCount = 0;
            for (int i = 0; i < trace.size(); i++) {
                long k = trace.keyAt(i);
                all.add(k);
                if (trace.isReadAt(i)) { reads.add(k); readCount++; } else writes.add(k);
                key.clear(); key.putLong(k); digest.update(key.array());
                digest.update((byte)(trace.isReadAt(i) ? 1 : 0));
            }
            System.out.println("{\"seed\":"+seed+",\"operations\":"+trace.size()
                    +",\"reads\":"+readCount+",\"writes\":"+(trace.size()-readCount)
                    +",\"distinctKeys\":"+all.size()+",\"distinctReadKeys\":"+reads.size()
                    +",\"distinctWriteKeys\":"+writes.size()+",\"residentKeysNotInTrace\":"+(32768-all.size())
                    +",\"residentKeysNeverUpdated\":"+(32768-writes.size())
                    +",\"traceSha256\":\""+HexFormat.of().formatHex(digest.digest())+"\"}");
        }
    }
}

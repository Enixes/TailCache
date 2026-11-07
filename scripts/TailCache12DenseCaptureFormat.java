import io.github.enixes.tailcache.workload.DenseObserverCapture;
import java.nio.file.Path;

/** Synthetic timestamps only, no cache/benchmark: exercise the retained recorder format. */
class TailCache12DenseCaptureFormat {
    public static void main(String[] args) throws Exception {
        var capture=new DenseObserverCapture(1,2,1);
        for(int phase=0;phase<3;phase++) {
            capture.resetIteration();long base=1_000_000_000L+phase*10_000_000L;
            capture.beginWindow(base);long previous=base;
            for(int op=0;op<1600;op++) {
                long start=previous+20,end=start+(op==800?1_200_000:10);
                capture.record(start,end,previous);previous=end;
            }
            capture.finishWindow(1600,previous);
        }
        capture.export(Path.of(args[0]).resolve("dense-observer"));
        System.out.println("synthetic=true cacheConstructed=false phases=3 operationsPerPhase=1600 stallsPerPhase=1");
    }
}

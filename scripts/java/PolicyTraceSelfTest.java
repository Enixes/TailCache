package io.github.enixes.tailcache.workload;

import io.github.enixes.tailcache.cache.*;
import java.nio.file.*;
import java.util.*;

/** Bounded functional qualification only; outputs are never research latency data. */
public final class PolicyTraceSelfTest {
    static void require(boolean test, String label) {
        if (!test) throw new IllegalStateException(label);
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("mode outputRoot");
        Path out=Path.of(args[1]);
        if (Files.exists(out)) throw new IllegalStateException("Refusing existing functional output");
        Files.createDirectories(out);
        if (args[0].equals("policy")) {
            CrossoverConfig config=new CrossoverConfig(128,512,24301,0,4096,0,128);
            List<CrossoverWorkload> work=new ArrayList<>();
            try {
                for (CrossoverBackend backend:CrossoverBackend.values()) {
                    work.add(new CrossoverWorkload(backend,config,1_000_003));
                    try (CacheAdapter cache=backend.create(config)) {
                        if (cache instanceof CaffeineCacheAdapter caffeine) {
                            for (long i=0;i<128;i++) cache.put(i,new byte[512]);
                            require((caffeine.frequencySketchSlotsForDiagnostic()>0)==caffeine.isBoundedForDiagnostic(),
                                    "Bounded/unbounded policy diagnostic");
                            require(caffeine.configurationSummary().contains("policy="),"Explicit policy log");
                        }
                    }
                }
                for (int i=0;i<10000;i++) {
                    byte[] expected=work.get(0).executeNext();
                    for (int j=1;j<work.size();j++)
                        require(Arrays.equals(expected,work.get(j).executeNext()),"Fresh value equality");
                }
                long expected=work.get(0).verifyContents();
                for (CrossoverWorkload w:work)
                    require(w.size()==128 && w.verifyContents()==expected,"Values/residents");
            } finally {
                for (CrossoverWorkload w:work) w.close();
            }
        } else if (args[0].equals("trace")) {
            for (int trace:new int[]{40_001,1_000_003}) {
                for (CrossoverBackend backend:new CrossoverBackend[]{CrossoverBackend.CAFFEINE,CrossoverBackend.CHRONICLE_IN_MEMORY}) {
                    Path worker=out.resolve(trace+"-"+backend);
                    TraceSensitivityRunner.main(new String[]{"--out",worker.toString(),"--backend",backend.name(),
                        "--payload","512","--residents","128","--live-mib","0","--churn-mib-sec","0",
                        "--qps","50000","--warmup-ms","0","--conditioning-ms","0","--measure-ms","100",
                        "--trace-operations",Integer.toString(trace)});
                    String configuration=Files.readString(worker.resolve("configuration.txt"));
                    require(configuration.contains("traceOperations="+trace+"\n"),"Trace selector");
                    require(configuration.contains("traceWriteOperations="+(trace==40_001?2000:50000)+"\n"),"Exact trace mix");
                    String completion=Files.readString(worker.resolve("completion.txt"));
                    require(completion.contains("scheduled=5000\ncompleted=5000\n") && completion.contains("status=OK"),
                            "Complete intended arrivals");
                    require(Files.readString(worker.resolve("integrity.txt")).contains("residentCount=128\n")
                            && Files.readString(worker.resolve("phase.txt")).equals("COMPLETE"),"Final values");
                }
            }
        } else throw new IllegalArgumentException("Unknown qualification mode");
        System.out.println("{\"passed\":true,\"mode\":\""+args[0]+"\",\"researchObservations\":0}");
    }
}

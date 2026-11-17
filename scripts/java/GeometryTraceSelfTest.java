package io.github.enixes.tailcache.workload;

import java.nio.file.*;
import java.util.*;

/** Source-matched geometry/pattern qualification; never research latency evidence. */
public final class GeometryTraceSelfTest {
    static void require(boolean value,String message) {
        if (!value) throw new IllegalStateException(message);
    }

    public static void main(String[] args) throws Exception {
        Path out=Path.of(args[0]);
        if (Files.exists(out)) throw new IllegalStateException("Refusing existing functional output");
        Files.createDirectories(out);
        long traceFields=Arrays.stream(GeometryWorkload.class.getDeclaredFields())
                .filter(field->field.getType()==WorkloadTrace.class).count();
        require(traceFields==1,"Only one trace retained by the experimental workload");
        CrossoverConfig config=new CrossoverConfig(32768,256,24301,0,4096,0,128);
        String previous=null;
        for (String pattern:new String[]{"uniform-long","repeated-short"}) {
            var generated=GeometryTraceFactory.generate(config,pattern);
            int writes=0;
            for (int i=0;i<generated.trace().size();i++) if (!generated.trace().isReadAt(i)) writes++;
            require(generated.trace().size()==1_000_003 && writes==50_000,"Equal geometry and exact operation mix");
            try (GeometryWorkload c=new GeometryWorkload(CrossoverBackend.CAFFEINE,config,1_000_003,pattern);
                 GeometryWorkload h=new GeometryWorkload(CrossoverBackend.CHRONICLE_IN_MEMORY,config,1_000_003,pattern)) {
                String metadata=c.traceConfiguration();
                require(metadata.contains("traceArrayPayloadBytes=9000027"),"Common array payload");
                require(metadata.contains("traceDistinctWriteKeys="+(pattern.equals("uniform-long")?25532:1939)+"\n"),
                        "Mutation coverage retained");
                require(c.traceFingerprint().equals(h.traceFingerprint()),"Matched pattern fingerprint");
                if (previous!=null) require(!previous.equals(c.traceFingerprint()),"Distinct treatments");
                previous=c.traceFingerprint();
                if (pattern.equals("uniform-long")) {
                    try (CrossoverWorkload original=new CrossoverWorkload(CrossoverBackend.CAFFEINE,config,1_000_003)) {
                        require(original.traceFingerprint().equals(c.traceFingerprint()),"Original uniform trace preserved");
                    }
                }
                for (int i=0;i<10000;i++) require(Arrays.equals(c.executeNext(),h.executeNext()),"Fresh value equality");
                require(c.verifyContents()==h.verifyContents() && c.size()==32768 && h.size()==32768,"Values/residents");
                Files.writeString(out.resolve(pattern+".properties"),metadata+"\ntraceSha256="+c.traceFingerprint()+"\n");
            }
            for (CrossoverBackend backend:new CrossoverBackend[]{CrossoverBackend.CAFFEINE,CrossoverBackend.CHRONICLE_IN_MEMORY}) {
                Path worker=out.resolve(pattern+"-"+backend);
                GeometryCrossoverRunner.main(new String[]{"--out",worker.toString(),"--backend",backend.name(),
                    "--payload","256","--residents","128","--live-mib","0","--churn-mib-sec","0",
                    "--qps","50000","--warmup-ms","0","--conditioning-ms","0","--measure-ms","100",
                    "--trace-pattern",pattern});
                String meta=Files.readString(worker.resolve("configuration.txt"));
                require(meta.contains("tracePattern="+pattern+"\n"),"Actual CLI treatment selection");
                require(Files.readString(worker.resolve("completion.txt")).contains("scheduled=5000\ncompleted=5000\n"),
                        "Functional request conservation");
                require(Files.readString(worker.resolve("phase.txt")).equals("COMPLETE"),"CLI value verification complete");
            }
        }
        System.out.println("{\"passed\":true,\"mode\":\"geometry\",\"researchObservations\":0}");
    }
}

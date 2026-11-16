package io.github.enixes.tailcache.workload;

/** Bounded functional validation only; no result enters the research dataset. */
public final class ServiceCrossoverSelfTest {
    static void require(boolean value, String label) {
        if (!value) throw new IllegalStateException(label);
    }
    public static void main(String[] args) {
        CrossoverConfig config = new CrossoverConfig(128, 512, 24301, 0, 4096, 0, 128);
        try (CrossoverWorkload c = new CrossoverWorkload(CrossoverBackend.CAFFEINE, config, ServiceCrossoverRunner.TRACE_SIZE);
             CrossoverWorkload h = new CrossoverWorkload(CrossoverBackend.CHRONICLE_IN_MEMORY, config, ServiceCrossoverRunner.TRACE_SIZE)) {
            require(c.traceFingerprint().equals(h.traceFingerprint()), "Trace identity");
            require(c.traceConfiguration().contains("traceWriteOperations=50000"), "Exact mix");
            require(c.traceConfiguration().contains("traceDistinctKeys=128"), "Key coverage");
            for (int i=0; i<10000; i++) require(java.util.Arrays.equals(c.executeNext(), h.executeNext()), "Values");
            require(c.verifyContents()==h.verifyContents() && c.size()==128 && h.size()==128, "Integrity");
        }
        for (boolean supply : new boolean[]{false,true}) {
            try (CrossoverWorkload w = new CrossoverWorkload(CrossoverBackend.CAFFEINE, config, ServiceCrossoverRunner.TRACE_SIZE);
                 ApplicationChurn churn = new ApplicationChurn(0,4096,128)) {
                churn.start();
                var r = ServiceCrossoverRunner.run(w,churn,100_000_000,0,false,0,false,512,supply);
                churn.stop();
                require(r.operations()==r.service().getTotalCount(), "Operation conservation");
                require(r.writes()==r.updateService().getTotalCount(), "Update conservation");
                require(r.readService().getTotalCount()+r.updateService().getTotalCount()==r.operations(), "Read conservation");
                for (var v : r.service().recordedValues()) {
                    long upper=v.getValueIteratedTo();
                    require(v.getCountAtValueIteratedTo()==r.readService().getCountAtValue(upper)+r.updateService().getCountAtValue(upper), "Per-bin union");
                }
                w.verifyContents();
            }
        }
        System.out.println("{\"passed\":true,\"longTraceMix\":true,\"backendValues\":true,\"perBinReadUpdateUnion\":true,\"supplyFloor\":true}");
    }
}

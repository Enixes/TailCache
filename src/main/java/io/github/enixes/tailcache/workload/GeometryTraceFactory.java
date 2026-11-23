package io.github.enixes.tailcache.workload;

/** Setup-only trace treatments with equal primitive-array lengths/types. */
final class GeometryTraceFactory {
    static final int LENGTH=1_000_003;
    record Built(WorkloadTrace trace,int corrections) { }

    static Built generate(CrossoverConfig config,String pattern) {
        DeterministicWorkloadGenerator generator=new DeterministicWorkloadGenerator();
        if (pattern.equals("uniform-long"))
            return new Built(generator.generate(WorkloadSpec.uniform(LENGTH,config.residentEntries(),.95,config.seed())),0);
        if (!pattern.equals("repeated-short")) throw new IllegalArgumentException("Unknown geometry treatment");
        WorkloadTrace source=generator.generate(WorkloadSpec.uniform(40_001,config.residentEntries(),.95,config.seed()));
        boolean[] readKeys=new boolean[config.residentEntries()],writeKeys=new boolean[config.residentEntries()];
        for (int i=0;i<source.size();i++) {
            int key=(int)source.keyAt(i);
            if (source.isReadAt(i)) readKeys[key]=true; else writeKeys[key]=true;
        }
        long[] keys=new long[LENGTH];boolean[] reads=new boolean[LENGTH];int writes=0;
        for (int i=0;i<LENGTH;i++) {
            int position=i%source.size();keys[i]=source.keyAt(position);reads[i]=source.isReadAt(position);
            if (!reads[i]) writes++;
        }
        int corrections=0,target=50_000;
        for (int i=LENGTH-1;i>=0 && writes!=target;i--) {
            int key=(int)keys[i];
            if (writes<target && reads[i] && writeKeys[key]) {
                reads[i]=false;writes++;corrections++;
            } else if (writes>target && !reads[i] && readKeys[key]) {
                reads[i]=true;writes--;corrections++;
            }
        }
        if (writes!=target) throw new IllegalStateException("Exact geometry-treatment mix not achieved");
        // Only the long arrays escape; source and temporary coverage arrays are setup locals.
        return new Built(new WorkloadTrace(keys,reads),corrections);
    }
}

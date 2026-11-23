package io.github.enixes.tailcache.workload;
import java.util.Arrays;
public final class MechanismSelfTest {
 static void check(boolean b,String s){if(!b)throw new IllegalStateException(s);}
 public static void main(String[]args)throws Exception{
  var config=new CrossoverConfig(128,256,54801,0,4096,0,128);
  for(int hot:new int[]{8,128})for(int bps:new int[]{0,50,500})
   try(var c=new MechanismWorkload(CrossoverBackend.CAFFEINE,config,bps,hot);var h=new MechanismWorkload(CrossoverBackend.CHRONICLE_IN_MEMORY,config,bps,hot)){
    for(int phase=0;phase<7;phase++)for(int i=0;i<10003;i++)check(Arrays.equals(c.executeNext(),h.executeNext()),"Backend values");
    check(c.operations()==70021&&c.operations()==h.operations()&&c.writes()==h.writes(),"Continuous counters");
    check(c.verifyContents()==h.verifyContents()&&c.traceFingerprint().equals(h.traceFingerprint()),"Contents/identity");
   }
  for(var backend:new CrossoverBackend[]{CrossoverBackend.CAFFEINE,CrossoverBackend.CHRONICLE_IN_MEMORY})
   try(var old=new PredictorWorkload(backend,config,500);var next=new MechanismWorkload(backend,config,500,128)){
    for(int i=0;i<50003;i++)check(Arrays.equals(old.executeNext(),next.executeNext()),"Full-set legacy equivalence");
    check(old.verifyContents()==next.verifyContents(),"Legacy final values");
   }
  for (var backend : new CrossoverBackend[]{CrossoverBackend.CAFFEINE, CrossoverBackend.CHRONICLE_IN_MEMORY})
   for (int stride : new int[]{1, 8}) checkWriteTiming(backend, config, stride);
  System.out.println("{\"passed\":true,\"pairedCases\":6,\"legacyFullSetEquivalent\":true,\"splitWriteEquivalent\":true,\"researchObservations\":0}");
 }

 private static void checkWriteTiming(CrossoverBackend backend, CrossoverConfig config, int stride) throws Exception {
   try (var original = new MechanismWorkload(backend, config, 500, 128);
        var instrumented = new MechanismWorkload(backend, config, 500, 128)) {
    for (int i = 0; i < 1003; i++) check(Arrays.equals(original.executeNext(), instrumented.executeNext()), "Prefix values");
    long writesBefore = instrumented.writes();
    var timing = new MechanismWorkload.WriteTiming(writesBefore, stride, config.seed());
    long samples = 0;
    for (int i = 0; i < 20003; i++) {
     long priorWrites = instrumented.writes();
     timing.constructionNs = -1;
     timing.cachePutNs = -1;
     check(Arrays.equals(original.executeNext(), instrumented.executeNext(timing)), "Split timing value mismatch");
     long ordinal = instrumented.writes() - writesBefore;
     boolean sampled = instrumented.writes() > priorWrites
         && (ordinal - 1) % stride == Math.floorMod(config.seed(), stride);
     if (sampled) {
      check(timing.recorded, "Selected write was not recorded");
      check(timing.constructionNs >= 0 && timing.cachePutNs >= 0, "Missing write durations");
      samples++;
     } else {
      check(timing.constructionNs == -1 && timing.cachePutNs == -1, "Unselected operation recorded a write duration");
     }
    }
    long writes = instrumented.writes() - writesBefore;
    long expected = (writes + stride - 1 - Math.floorMod(config.seed(), stride)) / stride;
    check(samples > 0 && samples == expected && original.writes() == instrumented.writes(), "Split timing count mismatch");
    check(original.verifyContents() == instrumented.verifyContents()
        && original.mutationVersionDigest().equals(instrumented.mutationVersionDigest()), "Split timing mutations differ");
   }
 }
}

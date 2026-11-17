package io.github.enixes.tailcache.workload;
import java.util.Arrays;
public final class PredictorSelfTest {
    private static void check(boolean b,String s){if(!b)throw new IllegalStateException(s);}
    public static void main(String[] args)throws Exception {
        for(int bps:new int[]{0,50,100,200,500}){
            var a=new PredictorStream(24301,32768,bps);var b=new PredictorStream(24301,32768,bps);long writes=0;boolean[] hit=new boolean[32768];
            for(long i=0;i<2_200_000;i++){check(a.keyAt(i)==b.keyAt(i)&&a.isReadAt(i)==b.isReadAt(i),"Pair stream");hit[a.keyAt(i)]=true;if(!a.isReadAt(i))writes++;}
            check(bps==0?writes==0:Math.abs(writes/2200000.0-bps/10000.0)<.001,"Write demand");
            for(boolean h:hit)check(h,"Uniform coverage");
        }
        var config=new CrossoverConfig(128,256,24301,0,4096,0,128);
        for(int bps:new int[]{0,500})try(var c=new PredictorWorkload(CrossoverBackend.CAFFEINE,config,bps);var h=new PredictorWorkload(CrossoverBackend.CHRONICLE_IN_MEMORY,config,bps)){
            var stream=new PredictorStream(24301,128,bps);long writes=0;
            for(int phase=0;phase<3;phase++)for(int j=0;j<10003;j++){long index=c.operations();check(Arrays.equals(c.executeNext(),h.executeNext()),"Backend values");if(!stream.isReadAt(index))writes++;}
            check(c.operations()==30009&&c.operations()==h.operations()&&c.writes()==writes&&h.writes()==writes,"Continuous phase count");
            check(c.verifyContents()==h.verifyContents(),"Contents");check(c.traceFingerprint().equals(h.traceFingerprint()),"Fingerprint");
        }
        System.out.println("{\"passed\":true,\"streamCases\":5,\"continuousPairedValues\":true,\"researchObservations\":0}");
    }
}

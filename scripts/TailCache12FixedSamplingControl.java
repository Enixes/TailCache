import org.openjdk.jmh.util.SampleBuffer;
import io.github.enixes.tailcache.workload.JmhSampleSelector;

/** Untimed known-population control for selection plus actual JMH buffer pipeline. */
class TailCache12FixedSamplingControl {
    public static void main(String[] args) {
        boolean pass=true;
        final int operations=1<<24;
        System.out.println("initial,pipeline,total,tailCount,tailFraction,p999Ns,halves");
        for(int initial:new int[]{0,1,-1}) {
            SampleBuffer adaptive=new SampleBuffer(),fixed=new SampleBuffer();
            int rnd=initial,mask=0,stride=0,halves=0;
            int[] phases=new int[512];
            for(int i=0;i<operations;i++) {
                rnd=rnd*1664525+1013904223;
                long value=i%100==0?20_000+64L*((i/100)%1024):100;
                if(JmhSampleSelector.select(rnd,mask)) {
                    adaptive.add(value);
                    if(stride++>20_000) {adaptive.half();stride=0;mask=(mask<<1)+1;halves++;}
                }
                if(JmhSampleSelector.select(rnd,15)) {fixed.add(value);phases[i%512]++;}
            }
            for(var pair:new Object[][]{{"adaptive",adaptive,halves},{"fixed15",fixed,0}}) {
                SampleBuffer b=(SampleBuffer)pair[1];var stats=b.getStatistics(1);long tail=0;
                var bins=stats.getRawData();
                while(bins.hasNext()) {var bin=bins.next();if(bin.getKey()>=20_000)tail+=bin.getValue();}
                double fraction=(double)tail/b.count(),p999=stats.getPercentile(99.9);
                System.out.printf("%d,%s,%d,%d,%.9f,%.1f,%d%n",initial,pair[0],b.count(),tail,fraction,p999,pair[2]);
                if(pair[0].equals("fixed15")) {
                    pass &= Math.abs(b.count()-operations/16.0)<=operations/16.0*.01;
                    pass &= fraction>=.008 && fraction<=.012 && p999>=20_000 && p999<=85_472;
                }
            }
            for(int n:phases)pass &= n>=1024 && n<=3072;
        }
        if(!pass)throw new AssertionError("Predeclared fixed-pipeline population/inclusion/phase bound failed");
    }
}

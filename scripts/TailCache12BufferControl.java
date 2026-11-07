import org.openjdk.jmh.util.SampleBuffer;

/** Setup-only actual pinned-JMH decimation counterexample; no cache or timing. */
class TailCache12BufferControl {
    public static void main(String[] args) {
        SampleBuffer buffer = new SampleBuffer();
        for(int i=0;i<100_000;i++)buffer.add(100);
        for(int i=0;i<100;i++)buffer.add(10_000+64L*i);
        System.out.println("halves,total,tailCount,tailFraction,p999Ns");
        for(int i=0;i<=8;i++) {
            var stats=buffer.getStatistics(1);
            long tail=0;
            var bins=stats.getRawData();
            while(bins.hasNext()) {var bin=bins.next();if(bin.getKey()>=10_000)tail+=bin.getValue();}
            System.out.printf("%d,%d,%d,%.9f,%.1f%n",i,buffer.count(),tail,(double)tail/buffer.count(),stats.getPercentile(99.9));
            if(tail!=100)throw new AssertionError("Pinned singleton-retention mechanism not reproduced");
            buffer.half();
        }
    }
}

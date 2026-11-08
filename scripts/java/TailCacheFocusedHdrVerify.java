import org.HdrHistogram.Histogram;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;

/** Independent post-collection exact compressed-HDR/bin verification. */
public final class TailCacheFocusedHdrVerify {
    public static void main(String[] args) throws Exception {
        int count=0;
        List<String> endpoints=new ArrayList<>();
        endpoints.add("path,count,p50Ns,p99Ns,p999Ns,p9999Ns,maxNs");
        try(var files=Files.walk(Path.of(args[0]))) {
            for(Path file:files.filter(p->p.toString().endsWith(".hdr")).toList()) {
                String stem=file.getFileName().toString().replace(".hdr","");
                var h=Histogram.decodeFromCompressedByteBuffer(ByteBuffer.wrap(Files.readAllBytes(file)),0);
                if(h.getNumberOfSignificantValueDigits()!=3 || h.getHighestTrackableValue()!=60_000_000_000L) throw new Exception("HDR configuration");
                List<String> lines=Files.readAllLines(file.resolveSibling(stem+"-bins.csv"));
                List<String> expected=new ArrayList<>();expected.add("upperEquivalentNs,count");
                for(var v:h.recordedValues()) expected.add(v.getValueIteratedTo()+","+v.getCountAtValueIteratedTo());
                if(!lines.equals(expected))throw new Exception("HDR/bin mismatch: "+file);
                var summary=Files.readAllLines(file.resolveSibling(stem+"-summary.csv")).get(1).split(",");
                if(Long.parseLong(summary[0])!=h.getTotalCount())throw new Exception("HDR count mismatch");
                // Optional derivative output: decode requested extreme percentiles
                // directly from HDR, independently of Python's rank calculation.
                if(args.length>1) endpoints.add("\""+file.toAbsolutePath().toString().replace("\"","\"\"")+"\","+h.getTotalCount()
                    +","+h.getValueAtPercentile(50)+","+h.getValueAtPercentile(99)+","+h.getValueAtPercentile(99.9)
                    +","+h.getValueAtPercentile(99.99)+","+h.getMaxValue());
                count++;
            }
        }
        if(count==0)throw new Exception("No histograms");
        if(args.length>1)Files.write(Path.of(args[1]),endpoints,StandardOpenOption.CREATE_NEW);
        System.out.println("{\"verifiedHistograms\":"+count+",\"distributionMatch\":true}");
    }
}

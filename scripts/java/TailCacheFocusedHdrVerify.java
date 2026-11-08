import org.HdrHistogram.Histogram;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;

/** Independent post-collection exact compressed-HDR/bin verification. */
public final class TailCacheFocusedHdrVerify {
    public static void main(String[] args) throws Exception {
        int count=0;
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
                count++;
            }
        }
        if(count==0)throw new Exception("No histograms");
        System.out.println("{\"verifiedHistograms\":"+count+",\"distributionMatch\":true}");
    }
}

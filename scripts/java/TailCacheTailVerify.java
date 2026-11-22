import org.HdrHistogram.Histogram;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Offline verification of bin resolution and strict exceedance count bounds. */
public final class TailCacheTailVerify {
    public static void main(String[] args) throws Exception {
        List<String> output = new ArrayList<>();
        output.add("path,count,bins,binBoundsSha256,gt100usLower,gt100usUpper,gt1msLower,gt1msUpper,gt10msLower,gt10msUpper");
        for (String name : Files.readAllLines(Path.of(args[0]))) {
            Path path = Path.of(name);
            Histogram h = Histogram.decodeFromCompressedByteBuffer(ByteBuffer.wrap(Files.readAllBytes(path)), 0);
            if (h.getLowestDiscernibleValue()!=1 || h.getNumberOfSignificantValueDigits()!=3
                || h.getHighestTrackableValue()!=60_000_000_000L) throw new Exception("Unexpected HDR resolution");
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            int bins=0;
            for (var bin : h.recordedValues()) {
                long upper=bin.getValueIteratedTo(), lower=h.lowestEquivalentValue(upper), count=bin.getCountAtValueIteratedTo();
                digest.update((lower+","+upper+","+count+"\n").getBytes(StandardCharsets.UTF_8));
                bins++;
            }
            String row="\""+name.replace("\"","\"\"")+"\","+h.getTotalCount()+","+bins+","+HexFormat.of().formatHex(digest.digest());
            for (long threshold : new long[]{100_000,1_000_000,10_000_000}) {
                long lower=0, upper=0;
                for (var bin : h.recordedValues()) {
                    if(h.lowestEquivalentValue(bin.getValueIteratedTo())>threshold)lower+=bin.getCountAtValueIteratedTo();
                    if(bin.getValueIteratedTo()>threshold)upper+=bin.getCountAtValueIteratedTo();
                }
                long directLower=h.getCountBetweenValues(h.nextNonEquivalentValue(threshold),Long.MAX_VALUE);
                long directUpper=h.getCountBetweenValues(threshold+1,Long.MAX_VALUE);
                if(lower!=directLower || upper!=directUpper)throw new Exception("HDR count range disagreement");
                row+=","+lower+","+upper;
            }
            output.add(row);
        }
        Files.write(Path.of(args[1]),output,StandardOpenOption.CREATE_NEW);
        System.out.println("{\"verifiedHistograms\":"+(output.size()-1)+"}");
    }
}

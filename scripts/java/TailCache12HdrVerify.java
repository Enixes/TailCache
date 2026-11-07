import org.HdrHistogram.Histogram;
import org.HdrHistogram.HistogramIterationValue;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Offline verifier only; never loaded by a benchmark worker. */
public final class TailCache12HdrVerify {
    public static void main(String[] args) throws Exception {
        Path worker=Path.of(args[0]);
        List<String> iterations=Files.readAllLines(worker.resolve("iterations.csv"));
        List<String> fields=List.of(iterations.getFirst().split(","));
        Set<Path> expected=new HashSet<>();
        int checked=0;
        for (String line:iterations.subList(1,iterations.size())) {
            String[] row=line.split(",",-1);
            String phase=row[fields.indexOf("phase")];
            if (phase.equals("WARMUP")) continue;
            if (!Set.of("CONDITIONING","MEASUREMENT").contains(phase)) throw new Exception("Unknown HDR phase");
            long operations=Long.parseLong(row[fields.indexOf("operations")]);
            if (operations<=0) throw new Exception("No completed operations");
            Path directory=phase.equals("CONDITIONING")?worker.resolve("conditioning"):worker;
            for (String channel:List.of("service","completion-gap")) {
                String stem="iteration-"+row[fields.indexOf("iteration")]+"-"+channel;
                Path file=directory.resolve(stem+".hdr");
                if (!expected.add(file)) throw new Exception("Duplicate HDR iteration");
                Histogram h=Histogram.decodeFromCompressedByteBuffer(ByteBuffer.wrap(Files.readAllBytes(file)),0);
                if (h.getTotalCount()!=operations || h.getNumberOfSignificantValueDigits()!=3
                        || h.getHighestTrackableValue()!=60_000_000_000L || h.getLowestDiscernibleValue()!=1)
                    throw new Exception("Invalid HDR count/configuration");
                try (BufferedReader reader=Files.newBufferedReader(directory.resolve(stem+"-bins.csv"))) {
                    if (!"upperEquivalentNs,count".equals(reader.readLine())) throw new Exception("Invalid bin header");
                    for (HistogramIterationValue value:h.recordedValues()) {
                        String expectedLine=value.getValueIteratedTo()+","+value.getCountAtValueIteratedTo();
                        if (!expectedLine.equals(reader.readLine())) throw new Exception("HDR/CSV distribution mismatch");
                    }
                    if (reader.readLine()!=null) throw new Exception("Extra CSV bin");
                }
                checked++;
            }
        }
        try (var files=Files.walk(worker)) {
            Set<Path> actual=new HashSet<>(files.filter(p->p.toString().endsWith(".hdr")).toList());
            if (!actual.equals(expected)) throw new Exception("Missing/extra HDR files");
        }
        if (checked==0) throw new Exception("No histograms verified");
        System.out.println("{\"verifiedHistograms\":"+checked+",\"distributionMatch\":true}");
    }
}

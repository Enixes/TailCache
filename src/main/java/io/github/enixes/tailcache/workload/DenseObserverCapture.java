package io.github.enixes.tailcache.workload;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Diagnostic-only common recording work, called after the cache end timestamp. */
public final class DenseObserverCapture {
    public static final String VERSION = "dense-observer-work-v1";
    private final int warmups;
    private final int conditioning;
    private final EveryOperationRecorder warmup = new EveryOperationRecorder();
    private final EveryOperationRecorder[] measured;
    private final long[] starts;
    private final long[] ends;
    private final long[] counts;
    private EveryOperationRecorder current;
    private int ordinal = -1;
    private boolean begun;
    private boolean finished = true;

    public DenseObserverCapture(int warmups, int physicalMeasurements, int conditioning) {
        if (warmups < 0 || physicalMeasurements < 1 || conditioning < 0 || conditioning >= physicalMeasurements) {
            throw new IllegalArgumentException("Invalid dense capture phases");
        }
        this.warmups = warmups;
        this.conditioning = conditioning;
        measured = new EveryOperationRecorder[physicalMeasurements];
        for (int i=0; i<measured.length; i++) measured[i] = new EveryOperationRecorder();
        starts = new long[warmups+physicalMeasurements];
        ends = new long[starts.length];
        counts = new long[starts.length];
    }

    public void resetIteration() {
        if (!finished || ordinal+1 >= counts.length) throw new IllegalStateException("Dense iteration order/coverage");
        ordinal++;
        current = ordinal < warmups ? warmup : measured[ordinal-warmups];
        current.reset();
        begun = false;
        finished = false;
    }

    public void beginWindow(long start) {
        if (ordinal < 0 || begun || finished || start <= 0) throw new IllegalStateException("Invalid dense window start");
        starts[ordinal] = start;
        begun = true;
    }

    public void record(long start, long end, long previousEnd) {
        current.record(start,end,previousEnd);
    }

    public void finishWindow(long operations, long end) {
        if (!begun || finished || operations <= 0 || current.operations() != operations
                || current.recordedCount() != operations || current.overflowCount() != 0 || end <= starts[ordinal]) {
            throw new IllegalStateException("Incomplete/overflowed dense window");
        }
        counts[ordinal] = operations;
        ends[ordinal] = end;
        finished = true;
    }

    public void export(Path directory) throws IOException {
        if (!finished || ordinal != counts.length-1) throw new IllegalStateException("Incomplete dense phase coverage");
        Files.createDirectory(directory);
        if (conditioning > 0) Files.createDirectory(directory.resolve("conditioning"));
        Files.writeString(directory.resolve("configuration.txt"), "version="+VERSION+"\nwarmups="+warmups
                +"\nphysicalMeasurements="+measured.length+"\nconditioning="+conditioning
                +"\nhistogramSignificantDigits=3\nhistogramMaxNs="+EveryOperationRecorder.MAX_NS+"\n");
        try (var writer = Files.newBufferedWriter(directory.resolve("iterations.csv"))) {
            writer.write("phase,iteration,startNs,endNs,operations,serviceAbove1ms,gapAbove1ms,serviceAbove10ms,gapAbove10ms,serviceMaxNs,completionGapMaxNs,eventCount,overflowCount\n");
            for (int i=0; i<counts.length; i++) {
                String phase = i < warmups ? "WARMUP" : i < warmups+conditioning ? "CONDITIONING" : "MEASUREMENT";
                int index = i < warmups ? i+1 : i < warmups+conditioning ? i-warmups+1 : i-warmups-conditioning+1;
                EveryOperationRecorder recorder = i < warmups ? null : measured[i-warmups];
                // Reused warmup histograms are not retained; empty fields mean unavailable.
                String tail = recorder == null ? ",,,,,,,," : ","+recorder.serviceAbove1ms()+","+recorder.gapAbove1ms()
                        +","+recorder.serviceAbove10ms()+","+recorder.gapAbove10ms()+","+recorder.serviceMaxNs()
                        +","+recorder.gapMaxNs()+","+recorder.stallEventCount()+","+recorder.overflowCount();
                writer.write(phase+","+index+","+starts[i]+","+ends[i]+","+counts[i]+tail+"\n");
            }
        }
        for (int i=0; i<measured.length; i++) {
            boolean prepared = i < conditioning;
            measured[i].export(prepared ? directory.resolve("conditioning") : directory,
                    "iteration-"+(prepared ? i+1 : i-conditioning+1));
        }
    }
}

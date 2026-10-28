package io.github.enixes.tailcache.workload;

import org.HdrHistogram.Histogram;
import org.HdrHistogram.HistogramIterationValue;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Preallocated, single-writer recorder. Export happens only after the worker window. */
public final class EveryOperationRecorder {
    public static final long MAX_NS = 60_000_000_000L;
    public static final long EVENT_THRESHOLD_NS = 1_000_000L;
    public static final int BRANCH_WARMUP_OPERATIONS = 40_000;
    private static volatile long branchWarmupChecksum;
    private final Histogram service = new Histogram(1, MAX_NS, 3);
    private final Histogram completionGap = new Histogram(1, MAX_NS, 3);
    private final long[][] events = new long[4096][5];
    private int eventCount;
    private long eventOverflow;
    private long histogramOverflow;
    private long operations;
    private long exactServiceMax;
    private long exactGapMax;
    private long serviceAbove1ms;
    private long gapAbove1ms;
    private long serviceAbove10ms;
    private long gapAbove10ms;

    public EveryOperationRecorder() {
        service.setAutoResize(false);
        completionGap.setAutoResize(false);
    }

    /** Train legitimate rare-stall paths before constructing any measured recorder. */
    public static void warmupBranches() {
        EveryOperationRecorder scratch = new EveryOperationRecorder();
        long checksum = 0;
        for (int i = 0; i < BRANCH_WARMUP_OPERATIONS; i++) {
            if ((i & 127) == 0) {
                checksum += scratch.servicePercentile(99.9) + scratch.gapMaxNs();
                scratch.reset();
            }
            // Synthetic timestamps exercise recorder code only: no workload, sleep or export.
            switch (i % 6) {
                case 0, 1 -> scratch.record(20_000_000, 20_000_100, 20_000_000);
                case 2 -> scratch.record(20_000_000, 21_000_000, 20_000_000);
                case 3 -> scratch.record(20_000_000, 20_000_100, 19_000_000);
                case 4 -> scratch.record(20_000_000, 30_000_000, 20_000_000);
                case 5 -> scratch.record(20_000_000, 20_000_100, 10_000_000);
                default -> throw new AssertionError();
            }
        }
        branchWarmupChecksum = checksum + scratch.servicePercentile(99.9)
                + scratch.recordedCount() + scratch.operations();
    }

    public void reset() {
        service.reset();
        completionGap.reset();
        eventCount = 0;
        eventOverflow = histogramOverflow = operations = 0;
        exactServiceMax = exactGapMax = 0;
        serviceAbove1ms = gapAbove1ms = serviceAbove10ms = gapAbove10ms = 0;
    }

    public void record(long startNs, long endNs, long previousCompletionNs) {
        long elapsed = endNs - startNs;
        long gap = endNs - previousCompletionNs;
        if (elapsed < 0 || gap < elapsed) throw new IllegalArgumentException("Nonmonotonic worker timestamps");
        operations++;
        exactServiceMax = Math.max(exactServiceMax, elapsed);
        exactGapMax = Math.max(exactGapMax, gap);
        if (elapsed >= EVENT_THRESHOLD_NS) serviceAbove1ms++;
        if (gap >= EVENT_THRESHOLD_NS) gapAbove1ms++;
        if (elapsed >= 10_000_000L) serviceAbove10ms++;
        if (gap >= 10_000_000L) gapAbove10ms++;
        if (elapsed > MAX_NS || gap > MAX_NS) histogramOverflow++;
        else {
            service.recordValue(elapsed);
            completionGap.recordValue(gap);
        }
        if (elapsed >= EVENT_THRESHOLD_NS || gap >= EVENT_THRESHOLD_NS) {
            if (eventCount == events.length) eventOverflow++;
            else {
                long[] event = events[eventCount++];
                event[0] = startNs; event[1] = endNs; event[2] = previousCompletionNs;
                event[3] = elapsed; event[4] = gap;
            }
        }
    }

    public long operations() { return operations; }
    public long serviceMaxNs() { return exactServiceMax; }
    public long gapMaxNs() { return exactGapMax; }
    public long serviceAbove1ms() { return serviceAbove1ms; }
    public long gapAbove1ms() { return gapAbove1ms; }
    public long serviceAbove10ms() { return serviceAbove10ms; }
    public long gapAbove10ms() { return gapAbove10ms; }
    public long recordedCount() { return service.getTotalCount(); }
    public long overflowCount() { return histogramOverflow + eventOverflow; }
    public long servicePercentile(double percentile) { return service.getValueAtPercentile(percentile); }

    public void export(Path directory, String stem) throws IOException {
        if (overflowCount() != 0 || service.getTotalCount() != operations || completionGap.getTotalCount() != operations) {
            throw new IllegalStateException("Incomplete/overflowed every-operation evidence");
        }
        exportHistogram(directory, stem + "-service", service);
        exportHistogram(directory, stem + "-completion-gap", completionGap);
        try (BufferedWriter writer = Files.newBufferedWriter(directory.resolve(stem + "-stall-events.csv"))) {
            writer.write("serviceStartNs,endNs,previousCompletionNs,serviceNs,completionGapNs\n");
            for (int i = 0; i < eventCount; i++) {
                long[] event = events[i];
                writer.write(event[0] + "," + event[1] + "," + event[2] + "," + event[3] + "," + event[4] + "\n");
            }
        }
    }

    private static void exportHistogram(Path directory, String stem, Histogram histogram) throws IOException {
        try (BufferedWriter writer = Files.newBufferedWriter(directory.resolve(stem + "-bins.csv"))) {
            writer.write("upperEquivalentNs,count\n");
            for (HistogramIterationValue value : histogram.recordedValues()) {
                writer.write(value.getValueIteratedTo() + "," + value.getCountAtValueIteratedTo() + "\n");
            }
        }
        ByteBuffer encoded = ByteBuffer.allocate(histogram.getNeededByteBufferCapacity());
        int bytes = histogram.encodeIntoCompressedByteBuffer(encoded);
        Files.write(directory.resolve(stem + ".hdr"), java.util.Arrays.copyOf(encoded.array(), bytes));
    }
}

import io.github.enixes.tailcache.cache.*;
import io.github.enixes.tailcache.workload.*;
import net.openhft.chronicle.map.ChronicleMap;
import org.HdrHistogram.Histogram;

import java.io.BufferedWriter;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Focused high-occupancy (88% -> 98%+) diagnostic harness to observe:
 * 1) Closed-loop service latency (p50, p99, p99.9, p99.99, max)
 * 2) Open-loop / coordinated-omission-corrected response latency at a fixed arrival rate
 * 3) GC pause count, total GC pause time, pause fraction, and post-GC heap occupancy
 * 4) Three backends:
 *    - CAFFEINE (on-heap)
 *    - CHRONICLE_IN_MEMORY (off-heap storage, allocating ordinary get())
 *    - CHRONICLE_GET_USING (off-heap storage, zero-allocation getUsing() into reusable buffer)
 */
public final class TailCache12CliffCrossoverProbe {
    private static volatile long blackhole;

    @SuppressWarnings("unchecked")
    private static ChronicleMap<Long, byte[]> extractChronicleMap(CacheAdapter adapter) throws Exception {
        Field f = ChronicleMapCacheAdapter.class.getDeclaredField("map");
        f.setAccessible(true);
        return (ChronicleMap<Long, byte[]>) f.get(adapter);
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> opts = new HashMap<>();
        for (int i = 0; i < args.length; i += 2) {
            opts.put(args[i], args[i + 1]);
        }
        String mode = opts.getOrDefault("--mode", "CAFFEINE"); // CAFFEINE, CHRONICLE_GET, CHRONICLE_GET_USING
        int residents = Integer.parseInt(opts.getOrDefault("--residents", "32768"));
        int payloadBytes = Integer.parseInt(opts.getOrDefault("--payload", "4096"));
        long liveBytes = Long.parseLong(opts.getOrDefault("--live-mib", "288")) * 1024L * 1024L;
        long churnBytesSec = Long.parseLong(opts.getOrDefault("--churn-mib-sec", "32")) * 1024L * 1024L;
        int warmups = Integer.parseInt(opts.getOrDefault("--warmups", "8"));
        int measurements = Integer.parseInt(opts.getOrDefault("--measurements", "8"));
        long targetQps = Long.parseLong(opts.getOrDefault("--target-qps", "100000")); // 100k ops/s open-loop schedule
        Path outFile = Path.of(opts.getOrDefault("--out", "/tmp/cliff-probe.json"));

        CrossoverBackend backendEnum = mode.equals("CAFFEINE")
                ? CrossoverBackend.CAFFEINE
                : CrossoverBackend.CHRONICLE_IN_MEMORY;
        boolean useGetUsing = mode.equals("CHRONICLE_GET_USING");

        CrossoverConfig config = new CrossoverConfig(
                residents, payloadBytes, 24301L,
                liveBytes, 4096, churnBytesSec, 128);

        // Prepare lifecycle warmup
        CrossoverLifecycleWarmup.prepare(backendEnum, config);

        // Access internal fields of CrossoverWorkload or build equivalent state with optional getUsing
        CacheAdapter cache = backendEnum.create(config);
        ChronicleMap<Long, byte[]> rawChronicle = useGetUsing ? extractChronicleMap(cache) : null;
        byte[] reusableValue = new byte[payloadBytes];

        Long[] keys = new Long[residents];
        FreshValueGenerator values = new FreshValueGenerator();
        SyntheticKeyValueGenerator keyGen = new SyntheticKeyValueGenerator();
        for (int i = 0; i < keys.length; i++) {
            keys[i] = keyGen.keyForIndex(i);
            cache.put(keys[i], values.create(keys[i], 0, payloadBytes));
        }
        WorkloadTrace trace = new DeterministicWorkloadGenerator().generate(
                WorkloadSpec.uniform(CrossoverWorkload.TRACE_SIZE, keys.length, 0.95, config.seed()));
        RetainedApplicationData ballast = new RetainedApplicationData(liveBytes, 4096);

        Histogram serviceHist = new Histogram(1, 60_000_000_000L, 3);
        Histogram gapHist = new Histogram(1, 60_000_000_000L, 3);
        Histogram openLoopHist = new Histogram(1, 60_000_000_000L, 3);
        serviceHist.setAutoResize(false);
        gapHist.setAutoResize(false);
        openLoopHist.setAutoResize(false);

        long intervalStepNs = 1_000_000_000L / targetQps; // e.g. 10,000 ns for 100k QPS

        com.sun.management.ThreadMXBean threadBean =
                (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
        threadBean.setThreadAllocatedMemoryEnabled(true);
        long threadId = Thread.currentThread().threadId();

        List<GarbageCollectorMXBean> gcBeans = ManagementFactory.getGarbageCollectorMXBeans();

        try (ApplicationChurn churn = new ApplicationChurn(churnBytesSec, 4096, 128)) {
            long totalOps = 0;
            long totalWrites = 0;
            long totalWorkerAlloc = 0;
            long totalChurnAlloc = 0;
            long totalChurnDropped = 0;
            long stallsOver1ms = 0;
            long stallsOver10ms = 0;
            long totalStallNsOver1ms = 0;

            long gcCountBefore = 0;
            long gcTimeMsBefore = 0;
            long measureStartWallNs = 0;
            long measureEndWallNs = 0;

            int cursor = 0;
            long writes = 0;

            for (int iter = 0; iter < warmups + measurements; iter++) {
                boolean isMeasured = iter >= warmups;
                if (iter == warmups) {
                    serviceHist.reset();
                    gapHist.reset();
                    openLoopHist.reset();
                    gcCountBefore = gcBeans.stream().mapToLong(GarbageCollectorMXBean::getCollectionCount).sum();
                    gcTimeMsBefore = gcBeans.stream().mapToLong(GarbageCollectorMXBean::getCollectionTime).sum();
                    measureStartWallNs = System.nanoTime();
                }

                churn.start();
                long allocBefore = threadBean.getThreadAllocatedBytes(threadId);
                long writesBefore = writes;
                long startNs = System.nanoTime();
                long deadlineNs = startNs + 1_000_000_000L;
                long prevEndNs = startNs;
                long nextIntendedStartNs = startNs;
                long localOps = 0;
                long localSum = 0;

                do {
                    long opStart = System.nanoTime();
                    int pos = cursor++;
                    if (cursor == trace.size()) cursor = 0;
                    Long key = keys[(int) trace.keyAt(pos)];
                    if (trace.isReadAt(pos)) {
                        if (useGetUsing) {
                            byte[] res = rawChronicle.getUsing(key, reusableValue);
                            if (res == null) throw new IllegalStateException("Miss");
                            localSum += res[0];
                        } else {
                            byte[] res = cache.get(key);
                            if (res == null) throw new IllegalStateException("Miss");
                            localSum += res[0];
                        }
                    } else {
                        long v = ++writes;
                        byte[] fresh = values.create(key, v, payloadBytes);
                        cache.put(key, fresh);
                        localSum += fresh[0];
                    }
                    long opEnd = System.nanoTime();
                    localOps++;

                    if (isMeasured) {
                        long svc = opEnd - opStart;
                        long gap = opEnd - prevEndNs;
                        serviceHist.recordValue(Math.min(svc, 60_000_000_000L));
                        gapHist.recordValue(Math.min(gap, 60_000_000_000L));
                        // Coordinated-omission-corrected / open-loop schedule:
                        // If a pause of duration G > intervalStepNs occurred, requests arriving every
                        // intervalStepNs during the stall queued behind it.
                        if (gap >= 1_000_000L) {
                            stallsOver1ms++;
                            totalStallNsOver1ms += gap;
                        }
                        if (gap >= 10_000_000L) {
                            stallsOver10ms++;
                        }
                        openLoopHist.recordValueWithExpectedInterval(
                                Math.min(gap, 60_000_000_000L), intervalStepNs);
                    }
                    prevEndNs = opEnd;
                } while (prevEndNs < deadlineNs);

                blackhole += localSum;
                long allocAfter = threadBean.getThreadAllocatedBytes(threadId);
                ApplicationChurn.Snapshot churnSnap = churn.stop();

                if (isMeasured) {
                    totalOps += localOps;
                    totalWrites += (writes - writesBefore);
                    totalWorkerAlloc += (allocAfter - allocBefore);
                    totalChurnAlloc += churnSnap.allocatedBytes();
                    totalChurnDropped += churnSnap.droppedBytes();
                }
            }
            measureEndWallNs = System.nanoTime();
            long gcCountAfter = gcBeans.stream().mapToLong(GarbageCollectorMXBean::getCollectionCount).sum();
            long gcTimeMsAfter = gcBeans.stream().mapToLong(GarbageCollectorMXBean::getCollectionTime).sum();

            long ballSum = ballast.checksum();
            blackhole += ballSum;

            double elapsedSec = (measureEndWallNs - measureStartWallNs) / 1e9;
            double workerBPerOp = (double) totalWorkerAlloc / Math.max(1, totalOps);

            String json = String.format(Locale.ROOT,
                    "{\n" +
                    "  \"mode\": \"%s\",\n" +
                    "  \"payloadBytes\": %d,\n" +
                    "  \"residents\": %d,\n" +
                    "  \"liveMiB\": %d,\n" +
                    "  \"churnMiBPerSec\": %d,\n" +
                    "  \"elapsedSec\": %.3f,\n" +
                    "  \"totalOps\": %d,\n" +
                    "  \"opsPerSec\": %.1f,\n" +
                    "  \"workerAllocBytesPerOp\": %.1f,\n" +
                    "  \"churnDroppedMiB\": %.2f,\n" +
                    "  \"gcCount\": %d,\n" +
                    "  \"gcTimeMs\": %d,\n" +
                    "  \"stallsOver1ms\": %d,\n" +
                    "  \"stallsOver10ms\": %d,\n" +
                    "  \"totalStallMsOver1ms\": %.2f,\n" +
                    "  \"closedLoopSvcP50Us\": %.2f,\n" +
                    "  \"closedLoopSvcP99Us\": %.2f,\n" +
                    "  \"closedLoopSvcP999Us\": %.2f,\n" +
                    "  \"closedLoopSvcP9999Us\": %.2f,\n" +
                    "  \"closedLoopSvcMaxMs\": %.2f,\n" +
                    "  \"closedLoopGapP50Us\": %.2f,\n" +
                    "  \"closedLoopGapP99Us\": %.2f,\n" +
                    "  \"closedLoopGapP999Us\": %.2f,\n" +
                    "  \"closedLoopGapP9999Us\": %.2f,\n" +
                    "  \"closedLoopGapMaxMs\": %.2f,\n" +
                    "  \"openLoopRespP50Us\": %.2f,\n" +
                    "  \"openLoopRespP99Us\": %.2f,\n" +
                    "  \"openLoopRespP999Us\": %.2f,\n" +
                    "  \"openLoopRespP9999Us\": %.2f,\n" +
                    "  \"openLoopRespMaxMs\": %.2f\n" +
                    "}\n",
                    mode, payloadBytes, residents, liveBytes / (1024 * 1024), churnBytesSec / (1024 * 1024),
                    elapsedSec, totalOps, totalOps / elapsedSec, workerBPerOp,
                    totalChurnDropped / (1024.0 * 1024.0),
                    (gcCountAfter - gcCountBefore), (gcTimeMsAfter - gcTimeMsBefore),
                    stallsOver1ms, stallsOver10ms, totalStallNsOver1ms / 1e6,
                    serviceHist.getValueAtPercentile(50.0) / 1e3,
                    serviceHist.getValueAtPercentile(99.0) / 1e3,
                    serviceHist.getValueAtPercentile(99.9) / 1e3,
                    serviceHist.getValueAtPercentile(99.99) / 1e3,
                    serviceHist.getMaxValue() / 1e6,
                    gapHist.getValueAtPercentile(50.0) / 1e3,
                    gapHist.getValueAtPercentile(99.0) / 1e3,
                    gapHist.getValueAtPercentile(99.9) / 1e3,
                    gapHist.getValueAtPercentile(99.99) / 1e3,
                    gapHist.getMaxValue() / 1e6,
                    openLoopHist.getValueAtPercentile(50.0) / 1e3,
                    openLoopHist.getValueAtPercentile(99.0) / 1e3,
                    openLoopHist.getValueAtPercentile(99.9) / 1e3,
                    openLoopHist.getValueAtPercentile(99.99) / 1e3,
                    openLoopHist.getMaxValue() / 1e6
            );
            Files.writeString(outFile, json);
            System.out.print(json);
        } finally {
            cache.close();
        }
    }
}

package io.github.enixes.tailcache.workload;

import java.io.BufferedWriter;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.locks.LockSupport;

/** One worker, every-operation closed-loop timing; validation injection is explicit and separate. */
public final class CrossoverLatencyRunner {
    private static volatile long consumed;

    private CrossoverLatencyRunner() { }

    public static void main(String[] args) throws Exception {
        Map<String, String> options = new HashMap<>();
        if (args.length % 2 != 0) throw new IllegalArgumentException("Expected --option value pairs");
        for (int i = 0; i < args.length; i += 2) options.put(args[i], args[i + 1]);
        Path directory = Path.of(options.getOrDefault("--out", "build/reports/tailcache12/every-operation"));
        if (Files.exists(directory)) throw new IllegalStateException("Refusing existing output directory: " + directory);
        Files.createDirectories(directory);
        CrossoverBackend backend = CrossoverBackend.valueOf(options.getOrDefault("--backend", "CAFFEINE"));
        CrossoverConfig config = new CrossoverConfig(
                integer(options, "--residents", 8192), integer(options, "--payload", 256),
                Long.decode(options.getOrDefault("--seed", "0x5EED")),
                number(options, "--application-live-bytes", 0), 4096,
                number(options, "--churn-bytes-sec", 16 * 1024 * 1024), 128);
        int warmups = integer(options, "--warmup", 12);
        int measurements = integer(options, "--measure", 8);
        long durationNs = number(options, "--iteration-ms", 1000) * 1_000_000;
        String validation = options.getOrDefault("--validation", "none");
        boolean floor = Boolean.parseBoolean(options.getOrDefault("--timer-floor", "false"));
        if (warmups < 0 || measurements < 1 || durationNs <= 0
                || !java.util.Set.of("none", "long-operation", "gc").contains(validation)
                || (!validation.equals("none") && durationNs < 500_000_000)) {
            throw new IllegalArgumentException("Invalid timing or validation parameters");
        }
        EveryOperationRecorder warmupRecorder = new EveryOperationRecorder();
        EveryOperationRecorder[] measurementRecorders = new EveryOperationRecorder[measurements];
        for (int i = 0; i < measurements; i++) measurementRecorders[i] = new EveryOperationRecorder();
        try (CrossoverWorkload workload = new CrossoverWorkload(backend, config);
             ApplicationChurn churn = new ApplicationChurn(config.churnBytesPerSecond(), 4096, 128);
             BufferedWriter writer = Files.newBufferedWriter(directory.resolve("iterations.csv"))) {
            Files.writeString(directory.resolve("configuration.txt"), "backend=" + backend + "\nconfig=" + config
                    + "\nbackendConfig=" + workload.backendConfiguration() + "\ntraceSize=" + CrossoverWorkload.TRACE_SIZE
                    + "\ntraceSha256=" + workload.traceFingerprint()
                    + "\nvalueGenerator=" + FreshValueGenerator.VERSION + "\nvalidation=" + validation
                    + "\ntimerFloor=" + floor + "\npid=" + ProcessHandle.current().pid()
                    + "\njdkVersion=" + System.getProperty("java.version") + "\noptions=" + options
                    + "\nhistogramSignificantDigits=3\nhistogramMaxNs=" + EveryOperationRecorder.MAX_NS
                    + "\njvmArgs=" + ManagementFactory.getRuntimeMXBean().getInputArguments() + "\n");
            writer.write("phase,iteration,startNs,endNs,uptimeStartMs,uptimeEndMs,operations,serviceP50Ns,serviceP99Ns,"
                    + "serviceP999Ns,serviceMaxNs,completionGapMaxNs,serviceAbove1ms,gapAbove1ms,serviceAbove10ms,gapAbove10ms,"
                    + "churnPayloadBytes,churnPayloadBytesPerSecond,churnDroppedBytes,churnLateTicks,churnRetainedBytes,"
                    + "injectionStartNs,injectionEndNs,uptimeAnchorBeforeNs,uptimeAnchorAfterNs,churnJvmAllocatedBytes,writes\n");
            for (int i = 0; i < warmups + measurements; i++) {
                boolean measured = i >= warmups;
                int index = measured ? i - warmups + 1 : i + 1;
                EveryOperationRecorder recorder = measured ? measurementRecorders[index - 1] : warmupRecorder;
                recorder.reset();
                workload.resetTraceCursor();
                PauseInjector injector = measured && index == 1 && validation.equals("gc") ? new PauseInjector() : null;
                if (injector != null) injector.start();
                churn.start();
                long writesBefore = workload.writes();
                long anchorBefore = System.nanoTime();
                long uptimeStart = ManagementFactory.getRuntimeMXBean().getUptime();
                long anchorAfter = System.nanoTime();
                long start = System.nanoTime();
                long deadline = start + durationNs;
                long previousEnd = start;
                boolean injectedLongOperation = false;
                long localChecksum = 0;
                if (injector != null) injector.release();
                long end;
                try {
                    do {
                        long operationStart = System.nanoTime();
                        if (measured && index == 1 && validation.equals("long-operation")
                                && !injectedLongOperation && operationStart - start >= 200_000_000) {
                            long until = operationStart + 50_000_000;
                            while (System.nanoTime() < until) LockSupport.parkNanos(until - System.nanoTime());
                            injectedLongOperation = true;
                        }
                        if (floor) localChecksum++;
                        else {
                            byte[] value = workload.executeNext();
                            localChecksum += value[0];
                        }
                        end = System.nanoTime();
                        recorder.record(operationStart, end, previousEnd);
                        previousEnd = end;
                    } while (end < deadline);
                } finally {
                    consumed = localChecksum;
                }
                long uptimeEnd = ManagementFactory.getRuntimeMXBean().getUptime();
                ApplicationChurn.Snapshot allocation = churn.stop();
                if (injector != null) injector.finish();
                writer.write((measured ? "MEASUREMENT" : "WARMUP") + "," + index + "," + start + "," + end + ","
                        + uptimeStart + "," + uptimeEnd + "," + recorder.operations() + "," + recorder.servicePercentile(50)
                        + "," + recorder.servicePercentile(99) + "," + recorder.servicePercentile(99.9) + ","
                        + recorder.serviceMaxNs() + "," + recorder.gapMaxNs() + "," + recorder.serviceAbove1ms() + ","
                        + recorder.gapAbove1ms() + "," + recorder.serviceAbove10ms() + "," + recorder.gapAbove10ms() + ","
                        + allocation.allocatedBytes() + "," + allocation.realizedBytesPerSecond() + ","
                        + allocation.droppedBytes() + "," + allocation.lateTicks() + "," + allocation.retainedPayloadBytes()
                        + "," + (injector == null ? 0 : injector.before) + "," + (injector == null ? 0 : injector.after)
                        + "," + anchorBefore + "," + anchorAfter + "," + allocation.jvmAllocatedBytes()
                        + "," + (workload.writes() - writesBefore) + "\n");
                writer.flush();
                if (!measured && index == Math.max(1, warmups - 2)) workload.verifyContents();
            }
            for (int i = 0; i < measurements; i++) measurementRecorders[i].export(directory, "iteration-" + (i + 1));
            Files.writeString(directory.resolve("integrity.txt"), "contentChecksum=" + workload.verifyContents()
                    + "\napplicationChecksum=" + workload.applicationChecksum() + "\noperations=" + workload.operations()
                    + "\nwrites=" + workload.writes() + "\nconsumed=" + consumed + "\n");
        }
    }

    private static int integer(Map<String, String> options, String key, int fallback) {
        return Math.toIntExact(number(options, key, fallback));
    }

    private static long number(Map<String, String> options, String key, long fallback) {
        return Long.parseLong(options.getOrDefault(key, Long.toString(fallback)));
    }

    private static final class PauseInjector {
        private final CountDownLatch started = new CountDownLatch(1);
        private volatile long before;
        private volatile long after;
        private volatile Throwable failure;
        private final Thread worker = new Thread(() -> {
            try {
                started.await();
                long target = System.nanoTime() + 200_000_000;
                while (System.nanoTime() < target) LockSupport.parkNanos(target - System.nanoTime());
                before = System.nanoTime();
                System.gc(); // Validation only. Raw GC/safepoint logs must confirm a pause.
                after = System.nanoTime();
            } catch (Throwable error) { failure = error; }
        }, "tailcache-validation-gc");
        void start() { worker.start(); }
        void release() { started.countDown(); }
        void finish() throws InterruptedException {
            worker.join(10_000);
            if (worker.isAlive() || failure != null || after == 0) throw new IllegalStateException("GC injection failed", failure);
        }
    }
}

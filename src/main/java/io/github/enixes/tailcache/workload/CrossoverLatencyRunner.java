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
        boolean compilerDiagnostics = Boolean.parseBoolean(options.getOrDefault("--compiler-diagnostics", "false"));
        boolean compilerCounters = compilerDiagnostics
                || Boolean.parseBoolean(options.getOrDefault("--compiler-counters", "true"));
        java.lang.management.RuntimeMXBean runtime = ManagementFactory.getRuntimeMXBean();
        java.lang.management.CompilationMXBean compiler = compilerCounters
                ? ManagementFactory.getCompilationMXBean() : null;
        if (compilerCounters && (compiler == null || !compiler.isCompilationTimeMonitoringSupported())) {
            throw new IllegalStateException("Compiler-time evidence unavailable");
        }
        if (warmups < 0 || measurements < 1 || durationNs <= 0
                || !java.util.Set.of("none", "long-operation", "gc").contains(validation)
                || (!validation.equals("none") && durationNs < 500_000_000)) {
            throw new IllegalArgumentException("Invalid timing or validation parameters");
        }
        CrossoverLifecycleWarmup.prepare(backend, config);
        EveryOperationRecorder.warmupBranches();
        EveryOperationRecorder warmupRecorder = new EveryOperationRecorder();
        EveryOperationRecorder[] measurementRecorders = new EveryOperationRecorder[measurements];
        for (int i = 0; i < measurements; i++) measurementRecorders[i] = new EveryOperationRecorder();
        // Defer formatting, histogram queries, and file output until all worker windows have ended.
        java.util.List<Observation> observations = new java.util.ArrayList<>(warmups + measurements);
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
                    + "\nlifecycleWarmupTrials=" + CrossoverLifecycleWarmup.TRIALS
                    + "\nrecorderBranchWarmupOperations=" + EveryOperationRecorder.BRANCH_WARMUP_OPERATIONS
                    + "\ncompilerCounters=" + compilerCounters + "\ncompilerXml=" + compilerDiagnostics
                    + "\njvmArgs=" + runtime.getInputArguments() + "\n");
            writer.write("phase,iteration,startNs,endNs,uptimeStartMs,uptimeEndMs,operations,serviceP50Ns,serviceP99Ns,"
                    + "serviceP999Ns,serviceMaxNs,completionGapMaxNs,serviceAbove1ms,gapAbove1ms,serviceAbove10ms,gapAbove10ms,"
                    + "churnPayloadBytes,churnPayloadBytesPerSecond,churnDroppedBytes,churnLateTicks,churnRetainedBytes,"
                    + "injectionStartNs,injectionEndNs,uptimeAnchorBeforeNs,uptimeAnchorAfterNs,churnJvmAllocatedBytes,writes,compilerMs\n");
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
                long compilerBefore = compiler == null ? -1 : compiler.getTotalCompilationTime();
                long anchorBefore = System.nanoTime();
                long uptimeStart = runtime.getUptime();
                long anchorAfter = System.nanoTime();
                long start = System.nanoTime();
                long deadline = start + durationNs;
                // Campaign calls pass false in both phases. Keep phase/index checks outside
                // the hot method: they otherwise invalidate its OSR compilation at measurement.
                boolean injectLongOperation = measured && index == 1 && validation.equals("long-operation");
                if (injector != null) injector.release();
                TimedWindow window = runWindow(workload, recorder, start, deadline, floor, injectLongOperation);
                long end = window.endNs();
                long uptimeEnd = runtime.getUptime();
                long compilerMs = compiler == null ? -1 : compiler.getTotalCompilationTime() - compilerBefore;
                ApplicationChurn.Snapshot allocation = churn.stop();
                if (injector != null) injector.finish();
                observations.add(new Observation(measured, index, start, end, uptimeStart, uptimeEnd,
                        recorder.operations(), allocation, injector == null ? 0 : injector.before,
                        injector == null ? 0 : injector.after, anchorBefore, anchorAfter,
                        workload.writes() - writesBefore, compilerMs));
                if (!measured && index == Math.max(1, warmups - 2)) workload.verifyContents();
            }
            for (Observation observation : observations) {
                // Warmup histograms are reused; only their operation counts are exported.
                EveryOperationRecorder recorder = observation.measured()
                        ? measurementRecorders[observation.index() - 1] : null;
                ApplicationChurn.Snapshot allocation = observation.allocation();
                writer.write((observation.measured() ? "MEASUREMENT" : "WARMUP") + "," + observation.index()
                        + "," + observation.start() + "," + observation.end() + "," + observation.uptimeStart()
                        + "," + observation.uptimeEnd() + "," + observation.operations()
                        + "," + (recorder == null ? 0 : recorder.servicePercentile(50))
                        + "," + (recorder == null ? 0 : recorder.servicePercentile(99))
                        + "," + (recorder == null ? 0 : recorder.servicePercentile(99.9))
                        + "," + (recorder == null ? 0 : recorder.serviceMaxNs())
                        + "," + (recorder == null ? 0 : recorder.gapMaxNs())
                        + "," + (recorder == null ? 0 : recorder.serviceAbove1ms())
                        + "," + (recorder == null ? 0 : recorder.gapAbove1ms())
                        + "," + (recorder == null ? 0 : recorder.serviceAbove10ms())
                        + "," + (recorder == null ? 0 : recorder.gapAbove10ms())
                        + "," + allocation.allocatedBytes() + "," + allocation.realizedBytesPerSecond()
                        + "," + allocation.droppedBytes() + "," + allocation.lateTicks() + "," + allocation.retainedPayloadBytes()
                        + "," + observation.injectionStart() + "," + observation.injectionEnd()
                        + "," + observation.anchorBefore() + "," + observation.anchorAfter()
                        + "," + allocation.jvmAllocatedBytes() + "," + observation.writes() + "," + observation.compilerMs() + "\n");
            }
            for (int i = 0; i < measurements; i++) measurementRecorders[i].export(directory, "iteration-" + (i + 1));
            Files.writeString(directory.resolve("integrity.txt"), "contentChecksum=" + workload.verifyContents()
                    + "\napplicationChecksum=" + workload.applicationChecksum() + "\noperations=" + workload.operations()
                    + "\nwrites=" + workload.writes() + "\nconsumed=" + consumed + "\n");
        }
    }

    static TimedWindow runWindow(CrossoverWorkload workload, EveryOperationRecorder recorder,
                                 long start, long deadline, boolean floor, boolean injectLongOperation) {
        long previousEnd = start;
        boolean injected = false;
        long localChecksum = 0;
        long end;
        try {
            do {
                long operationStart = System.nanoTime();
                if (injectLongOperation && !injected && operationStart - start >= 200_000_000) {
                    long until = operationStart + 50_000_000;
                    while (System.nanoTime() < until) LockSupport.parkNanos(until - System.nanoTime());
                    injected = true;
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
        return new TimedWindow(end, localChecksum);
    }

    record TimedWindow(long endNs, long checksum) { }

    private record Observation(boolean measured, int index, long start, long end, long uptimeStart,
                               long uptimeEnd, long operations, ApplicationChurn.Snapshot allocation,
                               long injectionStart, long injectionEnd, long anchorBefore,
                               long anchorAfter, long writes, long compilerMs) { }

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

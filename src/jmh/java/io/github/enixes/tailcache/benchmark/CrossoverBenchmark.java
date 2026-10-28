package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.workload.*;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.runner.IterationType;

import java.util.concurrent.TimeUnit;

@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 12, time = 1)
@Measurement(iterations = 8, time = 1)
@Fork(3)
public class CrossoverBenchmark {
    @State(Scope.Benchmark)
    public static class PressureState {
        @Param({"CAFFEINE", "CHRONICLE_IN_MEMORY"}) public CrossoverBackend backend;
        @Param({"256", "4096"}) public int payloadBytes;
        @Param({"8192"}) public int residentEntries;
        @Param({"0"}) public long applicationLiveBytes;
        @Param({"16777216"}) public long churnBytesPerSecond;
        @Param({"24301"}) public long seed;
        private CrossoverWorkload workload;
        private ApplicationChurn churn;
        private int warmups;
        private long operationsBefore;
        private long writesBefore;
        private final boolean compilerWindow = Boolean.getBoolean("tailcache12.compilerWindow");
        private java.lang.management.CompilationMXBean compiler;
        private long compilerStartMs;
        private java.nio.file.Path observationDirectory;
        private final java.util.ArrayList<IterationObservation> observations = new java.util.ArrayList<>();

        private record IterationObservation(IterationType phase, long operations, long writes,
                                            ApplicationChurn.Snapshot churn, long compilerMs) { }

        @Setup(Level.Trial)
        public void setup(BenchmarkParams params) {
            if (params.getThreads() != 1) throw new IllegalArgumentException("Crossover requires one cache worker");
            observations.ensureCapacity(params.getWarmup().getCount() + params.getMeasurement().getCount());
            observationDirectory = java.nio.file.Path.of(System.getProperty("tailcache12.observationDir",
                    "build/reports/tailcache12/unmanaged-observations"));
            try { java.nio.file.Files.createDirectories(observationDirectory); }
            catch (java.io.IOException failure) { throw new java.io.UncheckedIOException(failure); }
            CrossoverConfig config = new CrossoverConfig(residentEntries, payloadBytes, seed,
                    applicationLiveBytes, 4096, churnBytesPerSecond, 128);
            CrossoverLifecycleWarmup.prepare(backend, config);
            workload = new CrossoverWorkload(backend, config);
            churn = new ApplicationChurn(churnBytesPerSecond, 4096, 128);
            if (compilerWindow) compiler = java.lang.management.ManagementFactory.getCompilationMXBean();
            // JMH may include trial teardown in its final compiler-profiler envelope. Emit the
            // buffered observations only after the fork has returned its benchmark results.
            Runtime.getRuntime().addShutdownHook(new Thread(this::exportObservations, "tailcache-observation-export"));
            System.out.printf("[TailCache12] backend=%s config={%s} residents=%d payload=%d "
                            + "applicationLiveBytes=%d churnBytesPerSecond=%d seed=%d traceSize=%d traceSha256=%s valueGenerator=%s lifecycleWarmupTrials=%d%n",
                    backend, workload.backendConfiguration(), residentEntries, payloadBytes,
                    applicationLiveBytes, churnBytesPerSecond, seed, CrossoverWorkload.TRACE_SIZE, workload.traceFingerprint(), FreshValueGenerator.VERSION,
                    CrossoverLifecycleWarmup.TRIALS);
        }

        @Setup(Level.Iteration)
        public void startIteration() {
            workload.resetTraceCursor();
            operationsBefore = workload.operations();
            writesBefore = workload.writes();
            churn.start();
            if (compilerWindow) compilerStartMs = compiler.getTotalCompilationTime();
        }

        @TearDown(Level.Iteration)
        public void endIteration(IterationParams iteration, BenchmarkParams benchmark) {
            long workerCompilerMs = compilerWindow ? compiler.getTotalCompilationTime() - compilerStartMs : -1;
            ApplicationChurn.Snapshot snapshot = churn.stop();
            observations.add(new IterationObservation(iteration.getType(), workload.operations() - operationsBefore,
                    workload.writes() - writesBefore, snapshot, workerCompilerMs));
            if (iteration.getType() == IterationType.WARMUP) {
                warmups++;
                // Allocating full-value integrity check, followed by two settling warmups.
                if (warmups == Math.max(1, benchmark.getWarmup().getCount() - 2)) workload.verifyContents();
            }
        }

        private void exportObservations() {
            java.nio.file.Path output = observationDirectory.resolve("iterations-" + ProcessHandle.current().pid() + ".csv");
            try (java.io.BufferedWriter writer = java.nio.file.Files.newBufferedWriter(output,
                    java.nio.file.StandardOpenOption.CREATE_NEW)) {
                writer.write("phase,operations,writes,churnPayloadBytes,churnPayloadBytesPerSecond,churnJvmAllocatedBytes,"
                        + "churnDroppedBytes,lateTicks,retainedRingBytes,envelopeStartNs,envelopeEndNs,workerEnvelopeCompilerMs\n");
                for (IterationObservation observation : observations) {
                    ApplicationChurn.Snapshot snapshot = observation.churn();
                    writer.write(observation.phase() + "," + observation.operations() + "," + observation.writes()
                            + "," + snapshot.allocatedBytes() + "," + snapshot.realizedBytesPerSecond()
                            + "," + snapshot.jvmAllocatedBytes() + "," + snapshot.droppedBytes() + "," + snapshot.lateTicks()
                            + "," + snapshot.retainedPayloadBytes() + "," + snapshot.startNs() + "," + snapshot.endNs()
                            + "," + observation.compilerMs() + "\n");
                }
            } catch (java.io.IOException failure) {
                throw new java.io.UncheckedIOException("Unable to export iteration evidence", failure);
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            try {
                if (churn != null) churn.close();
                if (workload != null) {
                    System.out.printf("[TailCache12][integrity] checksum=%d applicationChecksum=%d operations=%d writes=%d%n",
                            workload.verifyContents(), workload.applicationChecksum(), workload.operations(), workload.writes());
                }
            } finally {
                if (workload != null) workload.close();
            }
        }
    }

    @Benchmark
    public void mixedWorkload(PressureState state, Blackhole blackhole) {
        blackhole.consume(state.workload.executeNext());
    }

    @Benchmark
    public void freshSupplyFloor(PressureState state, Blackhole blackhole) {
        blackhole.consume(state.workload.executeSupplyFloorNext());
    }
}

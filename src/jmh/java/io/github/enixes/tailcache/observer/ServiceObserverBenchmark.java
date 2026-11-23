package io.github.enixes.tailcache.observer;

import io.github.enixes.tailcache.workload.*;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.runner.IterationType;
import java.lang.management.ManagementFactory;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Independent JMH caller/sampler regime; no pooling with the custom recorder. */
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
public class ServiceObserverBenchmark {
    @State(Scope.Benchmark)
    public static class Pressure {
        @Param({"CAFFEINE","CHRONICLE_IN_MEMORY"}) public CrossoverBackend backend;
        @Param({"512","1024","4096"}) public int payload;
        @Param({"0","208"}) public int ballastMiB;
        private CrossoverWorkload work;
        private ApplicationChurn churn;
        private Path out;
        private boolean floor;
        private long floorOperations, operationsBefore, writesBefore, allocatedBefore, compileBefore, start;
        private int warmupOrdinal;
        private ApplicationChurn.Snapshot churnBefore;
        private final ArrayList<String> windows = new ArrayList<>(23);
        private String phase;
        private static volatile long consumed;

        @Setup(Level.Trial)
        public void setup(BenchmarkParams params) throws Exception {
            if(params.getThreads()!=1 || params.getOpsPerInvocation()!=1)
                throw new IllegalArgumentException("One cache worker/operation required");
            out=Path.of(System.getProperty("service.observationDir"));
            if(Files.exists(out))throw new IllegalStateException("Refusing existing worker output");
            Files.createDirectories(out);
            Files.writeString(out.resolve("worker.properties"),"pid="+ProcessHandle.current().pid()
                    +"\ncgroup="+Files.readString(Path.of("/proc/self/cgroup")).strip()
                    +"\nworkerAllocationCounters=true\n");
            if(Runtime.getRuntime().maxMemory()!=512L*1024*1024)
                throw new IllegalStateException("Workload fork must have a 512 MiB maximum heap");
            floor=params.getBenchmark().endsWith("timerFloor");
            int residents=floor?64:32768;
            CrossoverConfig config=new CrossoverConfig(residents,payload,24301,
                    (long)ballastMiB*1024*1024,4096,floor?0:32L*1024*1024,128);
            if(!CrossoverLifecycleWarmup.version().equals("none"))
                throw new IllegalStateException("Lightweight zero-maintenance lifecycle preparation required");
            CrossoverLifecycleWarmup.prepare(backend,config);
            work=new CrossoverWorkload(backend,config,1_000_003);
            churn=new ApplicationChurn(config.churnBytesPerSecond(),4096,128);
            Files.writeString(out.resolve("configuration.txt"),"backend="+backend+"\npayload="+payload
                    +"\nballastMiB="+ballastMiB+"\nresidents="+residents+"\nseed=24301\nconfig="+config
                    +"\nheapMaxBytes="+Runtime.getRuntime().maxMemory()
                    +"\nbackendConfig="+work.backendConfiguration()+"\n"+work.traceConfiguration()
                    +"\ntraceSha256="+work.traceFingerprint()+"\nreadContract=ordinary-get\n"
                    +"consumption=returned-value-byte-JMH-blackhole\ncontinuousChurn=true\nlightweightLifecycleTrials=3\njvmArgs="
                    +ManagementFactory.getRuntimeMXBean().getInputArguments()+"\n");
            windows.add("phase,startNs,endNs,operations,writes,workerAllocatedBytes,compilerMs,churnPayloadBytes,churnJvmAllocatedBytes,churnDroppedBytes");
            churn.start();
        }

        private long operations(){return floor?floorOperations:work.operations();}

        @Setup(Level.Iteration)
        public void before(IterationParams iteration) throws Exception {
            phase=iteration.getType()==IterationType.WARMUP
                    ?(++warmupOrdinal<=12?"WARMUP":"CONDITIONING"):"MEASUREMENT";
            Files.writeString(out.resolve("phase.txt"),phase);
            work.resetTraceCursor();
            operationsBefore=operations();writesBefore=work.writes();
            churnBefore=churn.snapshot();
            compileBefore=ManagementFactory.getCompilationMXBean().getTotalCompilationTime();
            allocatedBefore=WorkerAllocationCounter.currentBytes();
            start=System.nanoTime();
        }

        @TearDown(Level.Iteration)
        public void after() {
            long end=System.nanoTime();
            long allocation=WorkerAllocationCounter.currentBytes()-allocatedBefore;
            long compiler=ManagementFactory.getCompilationMXBean().getTotalCompilationTime()-compileBefore;
            var after=churn.snapshot();
            windows.add(String.format(Locale.ROOT,"%s,%d,%d,%d,%d,%d,%d,%d,%d,%d",phase,start,end,
                    operations()-operationsBefore,work.writes()-writesBefore,allocation,compiler,
                    after.allocatedBytes()-churnBefore.allocatedBytes(),after.jvmAllocatedBytes()-churnBefore.jvmAllocatedBytes(),
                    after.droppedBytes()-churnBefore.droppedBytes()));
        }

        @TearDown(Level.Trial)
        public void close() throws Exception {
            try {
                churn.stop();
                Files.write(out.resolve("windows.csv"),windows,StandardOpenOption.CREATE_NEW);
                Files.writeString(out.resolve("phase.txt"),"VERIFY");
                consumed=work.verifyContents();
                if(work.size()!=(floor?64:32768))throw new IllegalStateException("Resident count changed");
                Files.writeString(out.resolve("integrity.txt"),"passed=true\noperations="+operations()
                        +"\nwrites="+work.writes()+"\nresidentCount="+work.size()+"\nchecksum="+consumed+"\n");
                Files.writeString(out.resolve("phase.txt"),"COMPLETE");
            } finally {
                if(churn!=null)churn.close();
                if(work!=null)work.close();
            }
        }
    }

    @Benchmark
    public byte cacheAccess(Pressure state) {
        return state.work.executeNext()[0];
    }

    @Benchmark
    public byte timerFloor(Pressure state) {
        state.floorOperations++;
        return 0;
    }
}

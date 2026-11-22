package io.github.enixes.tailcache.workload;

import org.HdrHistogram.Histogram;
import java.lang.management.ManagementFactory;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.locks.LockSupport;

/** Separate ordinary-service follow-up: long trace and operation-specific diagnostics. */
public final class MechanismCrossoverRunner {
    private static volatile long consumed;
    private static final long MAX_NS = 60_000_000_000L;
    private static final int EVENT_LIMIT = 10_000;
    static final int WRITE_CLOCK_FLOOR_SAMPLES = 4096;
    public static final int TRACE_SIZE = 1_000_003;
    private MechanismCrossoverRunner() { }

    record Result(long start, long end, long offeredEnd, long operations, long scheduled,
                  long writes, long allocation, long compilerMs, long churnPayload,
                  long churnJvm, long churnDropped, long backlog, long eventCount, long overflowEvents,
                  long[] eventStarts, long[] eventEnds, long[] eventGapStarts, long[] eventIndexes,
                  Histogram service, Histogram gaps, Histogram response, Histogram readService, Histogram updateService,
                  Histogram valueConstruction, Histogram cachePut) { }

    public static void main(String[] args) throws Exception {
        if (args.length % 2 != 0) throw new IllegalArgumentException("Expected option/value pairs");
        Map<String,String> options = new HashMap<>();
        for (int i=0;i<args.length;i+=2) options.put(args[i],args[i+1]);
        Path out=Path.of(options.get("--out"));
        if (Files.exists(out)) throw new IllegalStateException("Refusing existing output");
        Files.createDirectories(out);
        String phase="SETUP";
        try {
            CrossoverBackend backend=CrossoverBackend.valueOf(options.getOrDefault("--backend","CAFFEINE"));
            int payload=Integer.parseInt(options.getOrDefault("--payload","4096"));
            int writeBps=Integer.parseInt(options.getOrDefault("--write-bps","500"));
            long live=Long.parseLong(options.getOrDefault("--live-mib","328"))*1024*1024;
            long rate=Long.parseLong(options.getOrDefault("--qps","0"));
            long warm=Long.parseLong(options.getOrDefault("--warmup-ms","8000"))*1_000_000;
            long conditioning=Long.parseLong(options.getOrDefault("--conditioning-ms","2000"))*1_000_000;
            long measured=Long.parseLong(options.getOrDefault("--measure-ms","8000"))*1_000_000;
            long inject=Long.parseLong(options.getOrDefault("--inject-stall-ms","0"))*1_000_000;
            boolean floor=Boolean.parseBoolean(options.getOrDefault("--floor","false"));
            boolean supply=Boolean.parseBoolean(options.getOrDefault("--supply-floor","false"));
            boolean splitWriteTiming = Boolean.parseBoolean(options.getOrDefault("--split-write-timing", "false"));
            if (splitWriteTiming && (floor || supply || writeBps == 0)) {
                throw new IllegalArgumentException("Split write timing requires actual cache writes");
            }
            int primeCalls=Integer.parseInt(options.getOrDefault("--prime-calls","0"));
            long primeNs=1_000_000_000L;
            if(primeCalls<0||primeCalls>4||warm<primeCalls*primeNs)throw new IllegalArgumentException("Priming contract");
            boolean reuse=Boolean.parseBoolean(options.getOrDefault("--reuse","false"));
            if (reuse || writeBps<0 || writeBps>10000) throw new IllegalArgumentException("Ordinary predictor configuration");
            if (rate<0 || rate>1_000_000 || rate>0 && 1_000_000_000L%rate!=0 || warm<0 || conditioning<0 || measured<=0 || inject<0 || inject>100_000_000)
                throw new IllegalArgumentException("Invalid timing controls");
            CrossoverConfig config=new CrossoverConfig(Integer.parseInt(options.getOrDefault("--residents","32768")),payload,
                Long.parseLong(options.getOrDefault("--seed","24301")),live,4096,
                Long.parseLong(options.getOrDefault("--churn-mib-sec","32"))*1024*1024,128);
            CrossoverLifecycleWarmup.prepare(backend,config,0);
            int hot=Integer.parseInt(options.getOrDefault("--update-hotset","0"));if(hot==0)hot=config.residentEntries();
            try (MechanismWorkload workload=new MechanismWorkload(backend,config,writeBps,hot);
                 ApplicationChurn churn=new ApplicationChurn(config.churnBytesPerSecond(),4096,128)) {
                Files.writeString(out.resolve("configuration.txt"),"backend="+backend+"\nconfig="+config+"\nbackendConfig="+workload.backendConfiguration()
                    +"\n"+workload.traceConfiguration()+"\ntraceSha256="+workload.traceFingerprint()+"\nvalueGenerator="+FreshValueGenerator.VERSION
                    +"\noptions="+options+"\njvmArgs="+ManagementFactory.getRuntimeMXBean().getInputArguments()
                    +"\nmaxHeapBytes="+Runtime.getRuntime().maxMemory()+"\nprimeCalls="+primeCalls+"\neventThresholdNs=100000\neventLimit="+EVENT_LIMIT+"\njdk="+System.getProperty("java.runtime.version")+"\npacing="+(rate>0?"fixed-arrival-spin-no-skips":"closed-loop")
                    +"\ncontinuousChurn=true\nlightweightLifecycleTrials=3\nreadContract="+(reuse?"borrowed-getUsing-buffer":"ordinary-get")+"\n");
                if (splitWriteTiming) {
                    Files.writeString(out.resolve("configuration.txt"), "splitWriteTiming=true\n",
                            java.nio.file.StandardOpenOption.APPEND);
                }
                churn.start();List<String> windows=new ArrayList<>();
                windows.add("phase,startNs,endNs,offeredEndNs,operations,scheduled,writes,workerAllocatedBytes,compilerMs,churnPayloadBytes,churnJvmAllocatedBytes,churnDroppedBytes,maxBacklog,stallEvents,unexportedStallEvents");
                List<String> phases=new ArrayList<>();for(int p=0;p<primeCalls;p++)phases.add("PRIME"+p);phases.addAll(List.of("WARMUP","CONDITIONING","MEASUREMENT"));
                for (String name:phases) {
                    phase=name;Files.writeString(out.resolve("phase.txt"),phase);
                    long streamStart=workload.operations();
                    long duration=name.startsWith("PRIME")?primeNs:name.equals("WARMUP")?warm-primeCalls*primeNs:name.equals("CONDITIONING")?conditioning:measured;
                    if (duration==0) continue;
                    // Stream position deliberately continues across every phase.
                    Result r=run(workload,churn,duration,rate,floor,name.equals("MEASUREMENT")?inject:0,reuse,payload,supply,splitWriteTiming);
                    Files.writeString(out.resolve("stream-"+name+".txt"),"start="+streamStart+"\nend="+workload.operations()+"\nwriteBps="+writeBps+"\n");
                    windows.add(String.format(Locale.ROOT,"%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",name,r.start,r.end,r.offeredEnd,
                        r.operations,r.scheduled,r.writes,r.allocation,r.compilerMs,r.churnPayload,r.churnJvm,r.churnDropped,r.backlog,r.eventCount,r.overflowEvents));
                    // No formatting/file IO occurs inside run's measured envelope.
                    if (name.equals("MEASUREMENT")) {
                        for (var entry:Map.of("service",r.service,"gap",r.gaps,"response",r.response,"read-service",r.readService,"update-service",r.updateService).entrySet()) export(out,entry.getKey(),entry.getValue());
                        if (splitWriteTiming) {
                            export(out, "write-value-construction", r.valueConstruction);
                            export(out, "write-cache-put", r.cachePut);
                        }
                        StringBuilder events=new StringBuilder("operationStartNs,operationEndNs,previousEndNs,operationIndex\n");
                        for (int i=0;i<Math.min(r.eventCount,EVENT_LIMIT);i++) events.append(r.eventStarts[i]).append(',').append(r.eventEnds[i]).append(',').append(r.eventGapStarts[i]).append(',').append(r.eventIndexes[i]).append('\n');
                        Files.writeString(out.resolve("stalls.csv"),events);
                        Files.writeString(out.resolve("completion.txt"),"scheduled="+r.scheduled+"\ncompleted="+r.operations+"\nunserved="+Math.max(0,r.scheduled-r.operations)
                            +"\nstatus="+(r.scheduled>0&&r.operations!=r.scheduled?"CENSORED":"OK")+"\n");
                    }
                }
                churn.stop();
                if (splitWriteTiming) {
                    export(out, "write-clock-floor", measureWriteClockFloor());
                }
                Files.write(out.resolve("windows.csv"),windows);
                phase="VERIFY";Files.writeString(out.resolve("phase.txt"),phase);
                Files.writeString(out.resolve("integrity.txt"),"contentChecksum="+workload.verifyContents()+"\napplicationChecksum="+workload.applicationChecksum()
                    +"\noperations="+workload.operations()+"\nwrites="+workload.writes()+"\nconsumed="+consumed+"\nmutationVersionSha256="+workload.mutationVersionDigest()+"\nresidentCount="+workload.size()+"\n");
                Files.writeString(out.resolve("phase.txt"),"COMPLETE");
            }
            if (Boolean.parseBoolean(options.getOrDefault("--observer-handshake", "false"))) {
                awaitObserver(out);
            }
        } catch (Throwable failure) {
            // A tiny failure record survives pressure OOM; stderr retains the full stack.
            try { Files.writeString(out.resolve("failure.txt"),"phase="+phase+"\nerror="+failure.getClass().getName()+"\nmessage="+failure.getMessage()+"\n"); }
            catch (Throwable ignored) { }
            throw failure;
        }
    }

    private static void awaitObserver(Path output) throws java.io.IOException {
        // Preserve the worker's CPU counters until the external observer can
        // bracket the end of measurement. No waiting occurs in a timed phase.
        Path ack = output.resolve("observer-ack.json");
        Files.createFile(output.resolve("observer-ready"));
        long started = System.nanoTime();
        while (!Files.exists(ack)) {
            if (System.nanoTime() - started >= 5_000_000_000L) {
                Files.createFile(output.resolve("observer-timeout"));
                return;
            }
            LockSupport.parkNanos(20_000_000L);
        }
    }

    static Result run(MechanismWorkload workload,ApplicationChurn churn,long duration,long qps,boolean floor,long inject,boolean reuse,int payload,boolean supply,
                      boolean splitWriteTiming) {
        // Same caller buffer footprint in both arms; ordinary reads do not use it.
        byte[] using=new byte[payload];
        Histogram readService=new Histogram(1,MAX_NS,3),updateService=new Histogram(1,MAX_NS,3);
        readService.setAutoResize(false);updateService.setAutoResize(false);
        Histogram service=new Histogram(1,MAX_NS,3),gaps=new Histogram(1,MAX_NS,3),response=new Histogram(1,MAX_NS,3);
        service.setAutoResize(false);gaps.setAutoResize(false);response.setAutoResize(false);
        MechanismWorkload.WriteTiming timing = splitWriteTiming ? new MechanismWorkload.WriteTiming() : null;
        Histogram valueConstruction = splitWriteTiming ? new Histogram(1, MAX_NS, 3) : null;
        Histogram cachePut = splitWriteTiming ? new Histogram(1, MAX_NS, 3) : null;
        long[] starts=new long[EVENT_LIMIT],ends=new long[EVENT_LIMIT],previous=new long[EVENT_LIMIT],indexes=new long[EVENT_LIMIT];
        var before=churn.snapshot();long writes=workload.writes(),allocated=WorkerAllocationCounter.currentBytes();
        var compiler=ManagementFactory.getCompilationMXBean();long compileBefore=compiler.getTotalCompilationTime();
        long start=System.nanoTime(),offeredEnd=start+duration,step=qps==0?0:1_000_000_000L/qps;
        ArrivalSchedule schedule=qps==0?null:new ArrivalSchedule(start,step,(duration+step-1)/step);
        long count=0,checksum=0,prevEnd=start,end=start,events=0,maxBacklog=0;boolean injected=false;long lastWrites=writes;
        while (schedule==null?end<offeredEnd:count<schedule.requests() && end<offeredEnd+10_000_000_000L) {
            long intended=schedule==null?0:schedule.intendedStart(count);
            if (schedule!=null) while (System.nanoTime()<intended) Thread.onSpinWait();
            long opStart=System.nanoTime();
            if (inject>0 && !injected && opStart>=start+200_000_000) {
                long until=opStart+inject;
                while (System.nanoTime()<until) LockSupport.parkNanos(until-System.nanoTime());
                injected=true;
            }
            if (supply) { Object value=workload.executeSupplyFloorNext(); checksum+=value instanceof byte[] array?array[0]:((Long)value).longValue(); }
            else checksum+=floor?1:workload.executeNext(timing)[0];
            end=System.nanoTime();
            long currentWrites=workload.writes();
            (currentWrites==lastWrites?readService:updateService).recordValue(end-opStart);
            if (splitWriteTiming && currentWrites != lastWrites) {
                valueConstruction.recordValue(timing.constructionNs);
                cachePut.recordValue(timing.cachePutNs);
            }
            lastWrites=currentWrites;
            service.recordValue(end-opStart);gaps.recordValue(end-prevEnd);
            if (schedule!=null) {
                response.recordValue(schedule.responseNs(count,end));
                maxBacklog=Math.max(maxBacklog,Math.max(0,schedule.offeredBy(opStart)-count));
            }
            if (end-prevEnd>=100_000) {
                if (events<EVENT_LIMIT) { starts[(int)events]=opStart;ends[(int)events]=end;previous[(int)events]=prevEnd;indexes[(int)events]=count; }
                events++;
            }
            count++;prevEnd=end;
        }
        long workerAllocation=WorkerAllocationCounter.currentBytes()-allocated,compiled=compiler.getTotalCompilationTime()-compileBefore;
        var after=churn.snapshot();consumed=checksum;
        if (service.getTotalCount()!=readService.getTotalCount()+updateService.getTotalCount()
                || updateService.getTotalCount()!=workload.writes()-writes) throw new IllegalStateException("Read/update conservation failed");
        if (splitWriteTiming && (valueConstruction.getTotalCount() != updateService.getTotalCount()
                || cachePut.getTotalCount() != updateService.getTotalCount())) {
            throw new IllegalStateException("Split write histogram count differs from update count");
        }
        return new Result(start,end,offeredEnd,count,schedule==null?0:schedule.requests(),workload.writes()-writes,
            workerAllocation,compiled,after.allocatedBytes()-before.allocatedBytes(),after.jvmAllocatedBytes()-before.jvmAllocatedBytes(),
            after.droppedBytes()-before.droppedBytes(),maxBacklog,events,Math.max(0,events-EVENT_LIMIT),starts,ends,previous,indexes,service,gaps,response,readService,updateService,
            valueConstruction,cachePut);
    }

    private static Histogram measureWriteClockFloor() {
        Histogram floor = new Histogram(1, MAX_NS, 3);
        for (int sample = 0; sample < WRITE_CLOCK_FLOOR_SAMPLES; sample++) {
            long start = System.nanoTime();
            long end = System.nanoTime();
            floor.recordValue(end - start);
        }
        return floor;
    }

    private static void export(Path out,String name,Histogram h) throws Exception {
        StringBuilder bins=new StringBuilder("upperEquivalentNs,count\n");
        for (var value:h.recordedValues()) bins.append(value.getValueIteratedTo()).append(',').append(value.getCountAtValueIteratedTo()).append('\n');
        Files.writeString(out.resolve(name+"-bins.csv"),bins);
        ByteBuffer encoded=ByteBuffer.allocate(h.getNeededByteBufferCapacity());h.encodeIntoCompressedByteBuffer(encoded);
        Files.write(out.resolve(name+".hdr"),java.util.Arrays.copyOf(encoded.array(),encoded.position()));
        Files.writeString(out.resolve(name+"-summary.csv"),"count,p50Ns,p99Ns,p999Ns,maxNs\n"+h.getTotalCount()+","+h.getValueAtPercentile(50)+","+h.getValueAtPercentile(99)+","+h.getValueAtPercentile(99.9)+","+h.getMaxValue()+"\n");
    }
}

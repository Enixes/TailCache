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

/** Short, outcome-preserving cliff experiment. Service and scheduled response are distinct. */
public final class FocusedCrossoverRunner {
    private static volatile long consumed;
    private static final long MAX_NS = 60_000_000_000L;
    private static final int EVENT_LIMIT = 10_000;
    private FocusedCrossoverRunner() { }

    record Result(long start, long end, long offeredEnd, long operations, long scheduled,
                  long writes, long allocation, long compilerMs, long churnPayload,
                  long churnJvm, long churnDropped, long backlog, long eventCount, long overflowEvents,
                  long[] eventStarts, long[] eventEnds, long[] eventGapStarts,
                  Histogram service, Histogram gaps, Histogram response) { }

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
            long live=Long.parseLong(options.getOrDefault("--live-mib","328"))*1024*1024;
            long rate=Long.parseLong(options.getOrDefault("--qps","0"));
            long warm=Long.parseLong(options.getOrDefault("--warmup-ms","8000"))*1_000_000;
            long conditioning=Long.parseLong(options.getOrDefault("--conditioning-ms","2000"))*1_000_000;
            long measured=Long.parseLong(options.getOrDefault("--measure-ms","8000"))*1_000_000;
            long inject=Long.parseLong(options.getOrDefault("--inject-stall-ms","0"))*1_000_000;
            boolean floor=Boolean.parseBoolean(options.getOrDefault("--floor","false"));
            if (rate<0 || rate>1_000_000 || rate>0 && 1_000_000_000L%rate!=0 || warm<0 || conditioning<0 || measured<=0 || inject<0 || inject>100_000_000)
                throw new IllegalArgumentException("Invalid timing controls");
            CrossoverConfig config=new CrossoverConfig(Integer.parseInt(options.getOrDefault("--residents","32768")),payload,
                Long.parseLong(options.getOrDefault("--seed","24301")),live,4096,
                Long.parseLong(options.getOrDefault("--churn-mib-sec","32"))*1024*1024,128);
            CrossoverLifecycleWarmup.prepare(backend,config,0);
            try (CrossoverWorkload workload=new CrossoverWorkload(backend,config);
                 ApplicationChurn churn=new ApplicationChurn(config.churnBytesPerSecond(),4096,128)) {
                Files.writeString(out.resolve("configuration.txt"),"backend="+backend+"\nconfig="+config+"\nbackendConfig="+workload.backendConfiguration()
                    +"\ntraceSha256="+workload.traceFingerprint()+"\nvalueGenerator="+FreshValueGenerator.VERSION
                    +"\noptions="+options+"\njvmArgs="+ManagementFactory.getRuntimeMXBean().getInputArguments()
                    +"\njdk="+System.getProperty("java.runtime.version")+"\npacing="+(rate>0?"fixed-arrival-spin-no-skips":"closed-loop")
                    +"\ncontinuousChurn=true\nlightweightLifecycleTrials=3\n");
                churn.start();List<String> windows=new ArrayList<>();
                windows.add("phase,startNs,endNs,offeredEndNs,operations,scheduled,writes,workerAllocatedBytes,compilerMs,churnPayloadBytes,churnJvmAllocatedBytes,churnDroppedBytes,maxBacklog,stallEvents,unexportedStallEvents");
                for (String name:List.of("WARMUP","CONDITIONING","MEASUREMENT")) {
                    phase=name;Files.writeString(out.resolve("phase.txt"),phase);
                    long duration=name.equals("WARMUP")?warm:name.equals("CONDITIONING")?conditioning:measured;
                    if (duration==0) continue;
                    workload.resetTraceCursor();
                    Result r=run(workload,churn,duration,rate,floor,name.equals("MEASUREMENT")?inject:0);
                    windows.add(String.format(Locale.ROOT,"%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",name,r.start,r.end,r.offeredEnd,
                        r.operations,r.scheduled,r.writes,r.allocation,r.compilerMs,r.churnPayload,r.churnJvm,r.churnDropped,r.backlog,r.eventCount,r.overflowEvents));
                    // No formatting/file IO occurs inside run's measured envelope.
                    if (name.equals("MEASUREMENT")) {
                        for (var entry:Map.of("service",r.service,"gap",r.gaps,"response",r.response).entrySet()) export(out,entry.getKey(),entry.getValue());
                        StringBuilder events=new StringBuilder("operationStartNs,operationEndNs,previousEndNs\n");
                        for (int i=0;i<Math.min(r.eventCount,EVENT_LIMIT);i++) events.append(r.eventStarts[i]).append(',').append(r.eventEnds[i]).append(',').append(r.eventGapStarts[i]).append('\n');
                        Files.writeString(out.resolve("stalls.csv"),events);
                        Files.writeString(out.resolve("completion.txt"),"scheduled="+r.scheduled+"\ncompleted="+r.operations+"\nunserved="+Math.max(0,r.scheduled-r.operations)
                            +"\nstatus="+(r.scheduled>0&&r.operations!=r.scheduled?"CENSORED":"OK")+"\n");
                    }
                }
                churn.stop();
                Files.write(out.resolve("windows.csv"),windows);
                phase="VERIFY";Files.writeString(out.resolve("phase.txt"),phase);
                Files.writeString(out.resolve("integrity.txt"),"contentChecksum="+workload.verifyContents()+"\napplicationChecksum="+workload.applicationChecksum()
                    +"\noperations="+workload.operations()+"\nwrites="+workload.writes()+"\nconsumed="+consumed+"\nresidentCount="+workload.size()+"\n");
                Files.writeString(out.resolve("phase.txt"),"COMPLETE");
            }
        } catch (Throwable failure) {
            // A tiny failure record survives pressure OOM; stderr retains the full stack.
            try { Files.writeString(out.resolve("failure.txt"),"phase="+phase+"\nerror="+failure.getClass().getName()+"\nmessage="+failure.getMessage()+"\n"); }
            catch (Throwable ignored) { }
            throw failure;
        }
    }

    static Result run(CrossoverWorkload workload,ApplicationChurn churn,long duration,long qps,boolean floor,long inject) {
        Histogram service=new Histogram(1,MAX_NS,3),gaps=new Histogram(1,MAX_NS,3),response=new Histogram(1,MAX_NS,3);
        service.setAutoResize(false);gaps.setAutoResize(false);response.setAutoResize(false);
        long[] starts=new long[EVENT_LIMIT],ends=new long[EVENT_LIMIT],previous=new long[EVENT_LIMIT];
        var before=churn.snapshot();long writes=workload.writes(),allocated=WorkerAllocationCounter.currentBytes();
        var compiler=ManagementFactory.getCompilationMXBean();long compileBefore=compiler.getTotalCompilationTime();
        long start=System.nanoTime(),offeredEnd=start+duration,step=qps==0?0:1_000_000_000L/qps;
        ArrivalSchedule schedule=qps==0?null:new ArrivalSchedule(start,step,(duration+step-1)/step);
        long count=0,checksum=0,prevEnd=start,end=start,events=0,maxBacklog=0;boolean injected=false;
        while (schedule==null?end<offeredEnd:count<schedule.requests() && end<offeredEnd+10_000_000_000L) {
            long intended=schedule==null?0:schedule.intendedStart(count);
            if (schedule!=null) while (System.nanoTime()<intended) Thread.onSpinWait();
            long opStart=System.nanoTime();
            if (inject>0 && !injected && opStart>=start+200_000_000) {
                long until=opStart+inject;
                while (System.nanoTime()<until) LockSupport.parkNanos(until-System.nanoTime());
                injected=true;
            }
            checksum+=floor?1:workload.executeNext()[0];end=System.nanoTime();
            service.recordValue(end-opStart);gaps.recordValue(end-prevEnd);
            if (schedule!=null) {
                response.recordValue(schedule.responseNs(count,end));
                maxBacklog=Math.max(maxBacklog,Math.max(0,schedule.offeredBy(opStart)-count));
            }
            if (end-prevEnd>=1_000_000) {
                if (events<EVENT_LIMIT) { starts[(int)events]=opStart;ends[(int)events]=end;previous[(int)events]=prevEnd; }
                events++;
            }
            count++;prevEnd=end;
        }
        long workerAllocation=WorkerAllocationCounter.currentBytes()-allocated,compiled=compiler.getTotalCompilationTime()-compileBefore;
        var after=churn.snapshot();consumed=checksum;
        return new Result(start,end,offeredEnd,count,schedule==null?0:schedule.requests(),workload.writes()-writes,
            workerAllocation,compiled,after.allocatedBytes()-before.allocatedBytes(),after.jvmAllocatedBytes()-before.jvmAllocatedBytes(),
            after.droppedBytes()-before.droppedBytes(),maxBacklog,events,Math.max(0,events-EVENT_LIMIT),starts,ends,previous,service,gaps,response);
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

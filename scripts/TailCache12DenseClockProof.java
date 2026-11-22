import io.github.enixes.tailcache.benchmark.CrossoverBenchmark;
import io.github.enixes.tailcache.benchmark.jmh_generated.*;
import io.github.enixes.tailcache.workload.JmhSampleSelectionEvidence;
import io.github.enixes.tailcache.workload.JmhSampleSelector;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.RawResults;
import org.openjdk.jmh.runner.InfraControl;
import org.openjdk.jmh.util.SampleBuffer;
import java.nio.file.Path;

/** Setup-only actual generated-stub clock routing proof; constructs no cache/workload. */
class TailCache12DenseClockProof {
    static final int LIMIT=4096;
    static final class Buffer extends SampleBuffer {
        boolean selected;
        long exact;
        int selections;
        @Override public void add(long value) {
            if(selected)throw new AssertionError("Missing full-capture callback");
            selected=true;exact=value;selections++;super.add(value);
        }
    }
    static final class State extends CrossoverBenchmark_PressureState_jmhType {
        final Buffer buffer;
        long previous,bodyStart,bodyEnd;
        int records;
        boolean inside,finished;
        State(Buffer buffer) {this.buffer=buffer;}
        @Override public void beginDenseWindow(long start) {previous=start;}
        @Override public void recordDense(long start,long end,long last) {
            if(inside || last!=previous || start>bodyStart || bodyStart>bodyEnd || bodyEnd>end)
                throw new AssertionError("Observer/timestamp boundary violation");
            if(buffer.selected && buffer.exact!=end-start)throw new AssertionError("Different selected/full timestamp pair");
            buffer.selected=false;previous=end;records++;
        }
        @Override public void finishDenseWindow(long count,long end) {
            if(count!=LIMIT || records!=LIMIT || end!=previous)throw new AssertionError("Window count/end mismatch");
            finished=true;
        }
    }
    static final class Benchmark extends CrossoverBenchmark_jmhType {
        final InfraControl control;
        int operations;
        Benchmark(InfraControl control) {this.control=control;}
        @Override public void mixedWorkload(CrossoverBenchmark.PressureState input,Blackhole ignored) {
            State state=(State)input;state.inside=true;
            state.bodyStart=System.nanoTime();
            operations++;state.bodyEnd=System.nanoTime();state.inside=false;
            if(operations==LIMIT)control.isDone=true;
        }
    }
    public static void main(String[] args) throws Throwable {
        if(args.length!=1)throw new IllegalArgumentException("Require fresh proof output directory");
        Class<?> actual=CrossoverBenchmark_mixedWorkload_jmhTest.class;
        if(!JmhSampleSelector.DENSE_VERSION.equals(actual.getField("TAILCACHE_SAMPLE_SELECTION_VERSION").get(null)))
            throw new AssertionError("Actual loaded class is not the common-observer overlay");
        System.setProperty("tailcache12.denseObserver","true");
        System.setProperty("tailcache12.sampleSelectionVersion",JmhSampleSelector.DENSE_VERSION);
        JmhSampleSelectionEvidence.write(Path.of(args[0]),actual);
        // Avoid constructing a JMH trial/worker: the stub reads only these two default-false control flags.
        var field=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");field.setAccessible(true);
        var unsafe=(sun.misc.Unsafe)field.get(null);
        var control=(InfraControl)unsafe.allocateInstance(InfraControl.class);
        var buffer=new Buffer();var state=new State(buffer);var benchmark=new Benchmark(control);var result=new RawResults();
        CrossoverBenchmark_mixedWorkload_jmhTest.mixedWorkload_sample_jmhStub(control,result,
            null,null,null,null,null,0,buffer,20_000,1,1,state,benchmark);
        if(!state.finished || benchmark.operations!=LIMIT || result.measuredOps!=LIMIT
                || buffer.selected || buffer.selections<=0 || buffer.selections>=LIMIT || buffer.count()!=buffer.selections)
            throw new AssertionError("Incomplete generated-stub routing proof");
        System.out.printf("operations=%d fullCaptures=%d selectedCaptures=%d identicalSelectedTimestampPairs=true observerOutsideBody=true%n",
            benchmark.operations,state.records,buffer.selections);
    }
}

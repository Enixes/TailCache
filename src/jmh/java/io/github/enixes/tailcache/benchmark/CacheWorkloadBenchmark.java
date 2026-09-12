package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Warmup;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.infra.ThreadParams;

import java.util.concurrent.TimeUnit;

/**
 * Mixed read/update workload benchmark for the primary TailCache matrix.
 *
 * <p>The cache itself is {@code Scope.Benchmark}, so runs with {@code -t > 1} are genuine
 * same-JVM shared-cache contention. The workload trace and replacement values are pre-generated;
 * measured work is limited to trace selection, one branch, and the selected cache operation.</p>
 */
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Measurement(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Fork(3)
public class CacheWorkloadBenchmark {

    @Benchmark
    public void mixedWorkload(
            CacheWorkloadState state,
            WorkloadCursorState cursor,
            ThreadParams threadParams,
            Blackhole blackhole
    ) {
        int traceIndex = cursor.nextTraceIndex(state.traceSize(), threadParams.getThreadIndex());
        Long key = state.keyAt(traceIndex);

        if (state.isReadAt(traceIndex)) {
            blackhole.consume(state.cache().get(key));
        } else {
            state.cache().put(key, state.replacementValueAt(traceIndex));
        }
    }
}

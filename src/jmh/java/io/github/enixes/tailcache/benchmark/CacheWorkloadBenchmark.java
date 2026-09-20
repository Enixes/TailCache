package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Warmup;
import org.openjdk.jmh.infra.Blackhole;

import java.util.concurrent.TimeUnit;

/**
 * Mixed read/existing-key-put workload benchmark for the primary TailCache matrix.
 *
 * <p>The cache itself is {@code Scope.Benchmark}, so runs with {@code -t > 1} are genuine
 * same-JVM shared-cache contention. The workload trace and replacement values are pre-generated;
 * per-worker cursor offsets are initialized outside measurement. The measured path resolves each
 * trace entry once, then performs the read/put branch and selected cache operation.</p>
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
            Blackhole blackhole
    ) {
        int traceIndex = cursor.nextTraceIndex();
        int logicalIndex = state.logicalIndexAt(traceIndex);
        Long key = state.keyForLogicalIndex(logicalIndex);

        if (state.isReadAt(traceIndex)) {
            blackhole.consume(state.cache().get(key));
        } else {
            state.cache().put(key, state.replacementValueForLogicalIndex(logicalIndex));
        }
    }
}

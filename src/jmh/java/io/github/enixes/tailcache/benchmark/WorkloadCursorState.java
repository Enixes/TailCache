package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.infra.ThreadParams;

/**
 * Per-worker cursor over the immutable pre-generated workload trace.
 *
 * <p>Each worker starts at a deterministic offset derived from its JMH thread index. The offset and
 * trace size are resolved during iteration setup so thread-index lookup and trace-size lookup are
 * not part of the measured cache operation. Workers still consume staggered positions of the same
 * deterministic cyclic trace; they are not independent per-thread traces.</p>
 */
@State(Scope.Thread)
public class WorkloadCursorState {

    private static final int THREAD_OFFSET_STRIDE = 8_191;

    private int cursor;
    private int traceSize;

    @Setup(Level.Iteration)
    public void setupIteration(CacheWorkloadState state, ThreadParams threadParams) {
        traceSize = state.traceSize();
        cursor = Math.floorMod(threadParams.getThreadIndex() * THREAD_OFFSET_STRIDE, traceSize);
    }

    public int nextTraceIndex() {
        int result = cursor++;
        if (cursor == traceSize) {
            cursor = 0;
        }
        return result;
    }
}

package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;

/**
 * Per-worker cursor over the immutable pre-generated workload trace.
 *
 * <p>Each worker starts at a deterministic offset derived from its JMH thread index. This avoids a
 * global cursor/atomic from becoming part of the measured operation while also preventing all
 * workers from replaying the same trace position in lockstep.</p>
 */
@State(Scope.Thread)
public class WorkloadCursorState {

    private static final int THREAD_OFFSET_STRIDE = 8_191;

    private int cursor;

    @Setup(Level.Iteration)
    public void setupIteration() {
        cursor = -1;
    }

    public int nextTraceIndex(int traceSize, int threadIndex) {
        if (cursor < 0) {
            cursor = Math.floorMod(threadIndex * THREAD_OFFSET_STRIDE, traceSize);
        }

        int result = cursor++;
        if (cursor == traceSize) {
            cursor = 0;
        }
        return result;
    }
}

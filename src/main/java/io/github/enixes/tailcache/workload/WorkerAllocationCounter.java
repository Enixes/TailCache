package io.github.enixes.tailcache.workload;

import java.lang.management.ManagementFactory;

/** Boundary-only allocation evidence; no counter read occurs per cache operation. */
public final class WorkerAllocationCounter {
    private static final com.sun.management.ThreadMXBean COUNTER = initialize();
    private WorkerAllocationCounter() { }

    private static com.sun.management.ThreadMXBean initialize() {
        if (!(ManagementFactory.getThreadMXBean() instanceof com.sun.management.ThreadMXBean counter)
                || !counter.isThreadAllocatedMemorySupported()) {
            throw new IllegalStateException("Worker allocation evidence is unavailable");
        }
        if (!counter.isThreadAllocatedMemoryEnabled()) counter.setThreadAllocatedMemoryEnabled(true);
        return counter;
    }

    public static long currentBytes() {
        long bytes = COUNTER.getThreadAllocatedBytes(Thread.currentThread().threadId());
        if (bytes < 0) throw new IllegalStateException("Worker allocation counter is unavailable");
        return bytes;
    }
}

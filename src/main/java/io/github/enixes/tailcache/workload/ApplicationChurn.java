package io.github.enixes.tailcache.workload;

import java.util.concurrent.locks.LockSupport;

/** Wall-clock offered allocation demand, independent of cache throughput; no catch-up bursts. */
public final class ApplicationChurn implements AutoCloseable {
    private static final long TICK_NS = 10_000_000;
    private static final int MAX_BATCH_OBJECTS = 256;
    private final long offeredBytesPerSecond;
    private final int objectBytes;
    private final byte[][] ring;
    private volatile boolean running;
    private volatile long checksum;
    private Thread thread;
    private volatile Throwable workerFailure;
    private final com.sun.management.ThreadMXBean allocationCounter;
    private volatile long workerAllocatedBytes = -1;
    private volatile long allocatedObjects;
    private volatile long droppedObjects;
    private volatile long lateTicks;
    private volatile long workerAllocationBase = -1;
    private long startedNs;
    private long stoppedNs;

    public ApplicationChurn(long offeredBytesPerSecond, int objectBytes, int ringSlots) {
        if (offeredBytesPerSecond < 0 || offeredBytesPerSecond > 1_000_000_000L
                || objectBytes < 64 || objectBytes > 32_768 || ringSlots < 1 || ringSlots > 16_384) {
            throw new IllegalArgumentException("Invalid churn settings");
        }
        this.offeredBytesPerSecond = offeredBytesPerSecond;
        this.objectBytes = objectBytes;
        ring = new byte[ringSlots][];
        java.lang.management.ThreadMXBean threads = java.lang.management.ManagementFactory.getThreadMXBean();
        allocationCounter = threads instanceof com.sun.management.ThreadMXBean counter
                && counter.isThreadAllocatedMemorySupported() ? counter : null;
        if (allocationCounter != null) allocationCounter.setThreadAllocatedMemoryEnabled(true);
    }

    public synchronized void start() {
        if (running || thread != null) throw new IllegalStateException("Churn already started");
        allocatedObjects = droppedObjects = lateTicks = 0;
        workerFailure = null;
        workerAllocatedBytes = offeredBytesPerSecond == 0 ? 0 : -1;
        workerAllocationBase = offeredBytesPerSecond == 0 ? 0 : -1;
        startedNs = System.nanoTime();
        running = true;
        if (offeredBytesPerSecond > 0) {
            thread = new Thread(() -> {
                long id = Thread.currentThread().threadId();
                long before = allocationCounter == null ? -1 : allocationCounter.getThreadAllocatedBytes(id);
                workerAllocationBase = before;
                try { allocate(); }
                catch (Throwable failure) { workerFailure = failure; }
                finally {
                    if (allocationCounter != null) workerAllocatedBytes = allocationCounter.getThreadAllocatedBytes(id) - before;
                }
            }, "tailcache-application-churn");
            thread.setDaemon(true);
            thread.start();
        }
    }

    /** Cumulative boundary observation without restarting the allocation thread. */
    public synchronized Snapshot snapshot() {
        if (!running) throw new IllegalStateException("Churn is not running");
        if (workerFailure != null) throw new IllegalStateException("Churn worker failed", workerFailure);
        long payload = allocatedObjects * objectBytes;
        long jvm = offeredBytesPerSecond == 0 ? 0 : allocationCounter == null || workerAllocationBase < 0
                ? -1 : allocationCounter.getThreadAllocatedBytes(thread.threadId()) - workerAllocationBase;
        int retained = 0;
        for (byte[] value : ring) if (value != null) retained++;
        return new Snapshot(offeredBytesPerSecond, payload, droppedObjects * objectBytes, lateTicks,
                startedNs, System.nanoTime(), (long) retained * objectBytes, checksum, jvm);
    }

    private void allocate() {
        long accounted = 0;
        long tick = startedNs + TICK_NS;
        while (running) {
            long now = System.nanoTime();
            if (now < tick) {
                LockSupport.parkNanos(this, tick - now);
                continue;
            }
            if (now - tick >= TICK_NS) lateTicks++;
            long due = (long) ((now - startedNs) * (offeredBytesPerSecond / 1e9) / objectBytes);
            long pending = Math.max(0, due - accounted);
            int batch = (int) Math.min(MAX_BATCH_OBJECTS, pending);
            droppedObjects += pending - batch;
            accounted = due; // A paused allocator does not replay an unbounded backlog.
            // Finish the admitted bounded work unit before observing stop again.
            // A per-object stop branch can remain untaken for many trials, then
            // invalidate allocate's compiled code at a late iteration boundary.
            // MAX_BATCH_OBJECTS bounds stop latency and no backlog is replayed.
            for (int i = 0; i < batch; i++) {
                byte[] object = new byte[objectBytes];
                long ordinal = allocatedObjects++;
                for (int j = 0; j < object.length; j++) object[j] = (byte) (ordinal * 31 + j);
                ring[(int) (ordinal % ring.length)] = object;
                checksum += object[0] + object[object.length - 1];
            }
            tick = now + TICK_NS;
        }
    }

    public synchronized Snapshot stop() {
        if (!running) throw new IllegalStateException("Churn is not running");
        running = false;
        if (thread != null) {
            LockSupport.unpark(thread);
            try {
                thread.join(10_000);
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("Interrupted stopping churn", exception);
            }
            if (thread.isAlive()) throw new IllegalStateException("Churn worker did not stop");
            thread = null;
        }
        stoppedNs = System.nanoTime();
        if (workerFailure != null) throw new IllegalStateException("Churn worker failed", workerFailure);
        int retained = 0;
        for (byte[] value : ring) if (value != null) retained++;
        return new Snapshot(offeredBytesPerSecond, allocatedObjects * objectBytes,
                droppedObjects * objectBytes, lateTicks, startedNs, stoppedNs,
                (long) retained * objectBytes, checksum, workerAllocatedBytes);
    }

    @Override
    public void close() { if (running) stop(); }

    public record Snapshot(long offeredBytesPerSecond, long allocatedBytes, long droppedBytes,
                           long lateTicks, long startNs, long endNs, long retainedPayloadBytes,
                           long checksum, long jvmAllocatedBytes) {
        public double realizedBytesPerSecond() {
            return allocatedBytes * 1e9 / Math.max(1, endNs - startNs);
        }
    }
}

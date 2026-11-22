package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.nio.file.Files;

import static org.junit.jupiter.api.Assertions.*;

class EveryOperationRecorderTest {
    @Test
    void branchWarmupCannotContaminateARealRecorder(@TempDir Path directory) throws Exception {
        EveryOperationRecorder real = new EveryOperationRecorder();
        EveryOperationRecorder.warmupBranches();
        assertEquals(0, real.operations());
        assertEquals(0, real.recordedCount());
        real.record(20_000_000, 20_000_100, 19_000_000);
        assertEquals(1, real.recordedCount());
        assertEquals(100, real.serviceMaxNs());
        assertEquals(1_000_100, real.gapMaxNs());
        assertEquals(0, real.serviceAbove1ms());
        assertEquals(1, real.gapAbove1ms());
        assertEquals(0, real.overflowCount());
        real.export(directory, "real-after-branch-warmup");
        assertEquals(2, Files.readAllLines(directory.resolve("real-after-branch-warmup-stall-events.csv")).size());
    }

    @Test
    void recordingUsesPreallocatedStorage() {
        com.sun.management.ThreadMXBean threads =
                (com.sun.management.ThreadMXBean) java.lang.management.ManagementFactory.getThreadMXBean();
        org.junit.jupiter.api.Assumptions.assumeTrue(threads.isThreadAllocatedMemorySupported());
        threads.setThreadAllocatedMemoryEnabled(true);
        EveryOperationRecorder recorder = new EveryOperationRecorder();
        for (int i = 0; i < 200_000; i++) recorder.record(10, 110, 0);
        long thread = Thread.currentThread().threadId();
        long before = threads.getThreadAllocatedBytes(thread);
        for (int i = 0; i < 200_000; i++) recorder.record(10, 110, 0);
        long allocated = threads.getThreadAllocatedBytes(thread) - before;
        assertTrue(allocated <= 4096, "Recorder allocated " + allocated + " bytes");
    }

    @Test
    void aPauseBetweenCallsIsRetainedAsCompletionGap(@TempDir Path directory) throws Exception {
        EveryOperationRecorder recorder = new EveryOperationRecorder();
        recorder.record(10, 110, 0);
        recorder.record(50_000_110, 50_000_210, 110);
        assertEquals(2, recorder.recordedCount());
        assertEquals(100, recorder.serviceMaxNs());
        assertEquals(50_000_100, recorder.gapMaxNs());
        assertEquals(0, recorder.serviceAbove10ms());
        assertEquals(1, recorder.gapAbove10ms());
        recorder.export(directory, "known-gap");
        assertTrue(Files.readString(directory.resolve("known-gap-stall-events.csv")).contains("50000100"));
    }

    @Test
    void overflowFailsClosedRatherThanClampingStalls(@TempDir Path directory) {
        EveryOperationRecorder recorder = new EveryOperationRecorder();
        recorder.record(0, EveryOperationRecorder.MAX_NS + 1, 0);
        assertEquals(1, recorder.overflowCount());
        assertThrows(IllegalStateException.class, () -> recorder.export(directory, "overflow"));
    }

    @Test
    void eventBufferOverflowAlsoRejectsEvidence(@TempDir Path directory) {
        EveryOperationRecorder recorder = new EveryOperationRecorder();
        for (int i = 0; i < 5000; i++) recorder.record(0, 2_000_000, 0);
        assertEquals(5000, recorder.recordedCount());
        assertEquals(904, recorder.overflowCount());
        assertThrows(IllegalStateException.class, () -> recorder.export(directory, "event-overflow"));
    }
}

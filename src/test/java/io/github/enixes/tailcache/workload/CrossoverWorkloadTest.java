package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.concurrent.locks.LockSupport;

import static org.junit.jupiter.api.Assertions.*;

class CrossoverWorkloadTest {
    private static CrossoverConfig config(int payload) {
        return new CrossoverConfig(128, payload, 0x5EEDL, 8193, 4096, 0, 16);
    }

    @Test
    void aFullTraceHasTheExactDeclaredMix() {
        try (CrossoverWorkload workload = new CrossoverWorkload(CrossoverBackend.CAFFEINE, config(256))) {
            for (int i = 0; i < CrossoverWorkload.TRACE_SIZE; i++) workload.executeNext();
            assertEquals(2_000, workload.writes());
            assertEquals(38_001, workload.reads());
            assertEquals(CrossoverWorkload.TRACE_WRITE_COUNT, workload.writes());
            assertEquals(CrossoverWorkload.TRACE_READ_COUNT, workload.reads());
            workload.verifyContents();
        }
        assertThrows(IllegalArgumentException.class, () ->
                new CrossoverConfig(32_769, 256, 0, 0, 4096, 0, 128));
    }

    @Test
    void jmhPowerOfTwoSamplingCanVisitEveryTracePosition() {
        // Replay the generated JMH1.37 recurrence, independently of workload
        // execution. A40000 period would visit only625 positions at stride256.
        int stride = 256;
        int[] visits = new int[CrossoverWorkload.TRACE_SIZE];
        int random = 123456789;
        for (int operation = 0; operation < visits.length * stride; operation++) {
            random = random * 1664525 + 1013904223;
            if ((random & (stride - 1)) == 0) visits[operation % visits.length]++;
        }
        for (int count : visits) assertEquals(1, count, "Permanently excluded or repeated trace phase");
    }

    @Test
    void reviewedLifecycleWriteContractsMatchTheActualGenerator() {
        long[] seeds = {24301, 0xC0FFEE, 0xBADC0DE};
        int[] expected = {383988, 383982, 383991};
        int perTrial = CrossoverLifecycleWarmup.MAINTENANCE_BATCHES * CrossoverLifecycleWarmup.BATCH_OPERATIONS;
        for (int s = 0; s < seeds.length; s++) {
            WorkloadTrace trace = new DeterministicWorkloadGenerator().generate(
                    WorkloadSpec.uniform(CrossoverWorkload.TRACE_SIZE, 32768, .95, seeds[s]));
            int writes = 0;
            for (int operation = 0; operation < perTrial; operation++) {
                if (!trace.isReadAt(operation % trace.size())) writes++;
            }
            assertEquals(expected[s], writes * CrossoverLifecycleWarmup.TRIALS);
        }
    }

    @Test
    void backendsHaveIdenticalFreshLogicalValuesAndStableResidents() {
        for (int payload : new int[]{256, 4096}) {
            try (CrossoverWorkload caffeine = new CrossoverWorkload(CrossoverBackend.CAFFEINE, config(payload));
                 CrossoverWorkload chronicle = new CrossoverWorkload(CrossoverBackend.CHRONICLE_IN_MEMORY, config(payload))) {
                assertEquals(caffeine.traceFingerprint(), chronicle.traceFingerprint());
                byte[] savedWrite = null;
                byte[] savedCopy = null;
                for (int operation = 0; operation < 20_000; operation++) {
                    long previousWrites = caffeine.writes();
                    byte[] value = caffeine.executeNext();
                    assertArrayEquals(value, chronicle.executeNext());
                    if (savedWrite == null && caffeine.writes() > previousWrites) {
                        savedWrite = value;
                        savedCopy = value.clone();
                    }
                }
                assertNotNull(savedWrite);
                assertArrayEquals(savedCopy, savedWrite, "Inserted value was mutated or recycled");
                assertTrue(caffeine.writes() > 0);
                assertEquals(caffeine.writes(), chronicle.writes());
                assertEquals(caffeine.verifyContents(), chronicle.verifyContents());
                assertEquals(128, caffeine.size());
                assertEquals(128, chronicle.size());
            }
        }
    }

    @Test
    void freshArraysHaveExclusiveOwnershipAndVersionedContents() {
        FreshValueGenerator generator = new FreshValueGenerator();
        byte[] a = generator.create(12, 1, 256);
        byte[] b = generator.create(12, 1, 256);
        assertNotSame(a, b);
        assertArrayEquals(a, b);
        assertFalse(Arrays.equals(a, generator.create(12, 2, 256)));
        assertFalse(Arrays.equals(a, generator.create(13, 1, 256)));
    }

    @Test
    void supplyFloorLeavesTheResidentValuesUntouched() {
        try (CrossoverWorkload workload = new CrossoverWorkload(CrossoverBackend.CAFFEINE, config(256))) {
            long initial = workload.verifyContents();
            for (int i = 0; i < 10_000; i++) assertNotNull(workload.executeSupplyFloorNext());
            assertTrue(workload.writes() > 0);
            assertEquals(initial, workload.verifyContents());
        }
    }

    @Test
    void applicationDataHasExactLogicalPayloadAndBoundedObjects() {
        RetainedApplicationData data = new RetainedApplicationData(8193, 4096);
        assertEquals(8193, data.payloadBytes());
        assertEquals(3, data.objectCount());
        assertEquals(data.checksum(), data.checksum());
        assertEquals(0, new RetainedApplicationData(0, 4096).checksum());
        RetainedApplicationData grouped = new RetainedApplicationData(8193, 64);
        assertEquals(129, grouped.objectCount());
        assertEquals(8193, grouped.payloadBytes());
        assertThrows(IllegalArgumentException.class, () -> new RetainedApplicationData(1, 1_000_000));
    }

    @Test
    void lifecycleWarmupDoesNotChangeTheMeasuredWorkloadState() {
        for (CrossoverBackend backend : CrossoverBackend.values()) {
            CrossoverConfig config = config(4096);
            CrossoverLifecycleWarmup.prepare(backend, config);
            try (CrossoverWorkload measured = new CrossoverWorkload(backend, config);
                 CrossoverWorkload reference = new CrossoverWorkload(backend, config)) {
                assertEquals(0, measured.operations());
                assertEquals(0, measured.writes());
                assertEquals(config.residentEntries(), measured.size());
                assertEquals(reference.verifyContents(), measured.verifyContents());
                assertEquals(reference.applicationChecksum(), measured.applicationChecksum());
                assertEquals(reference.traceFingerprint(), measured.traceFingerprint());
                for (int i = 0; i < CrossoverWorkload.TRACE_SIZE; i++) {
                    assertArrayEquals(reference.executeNext(), measured.executeNext());
                }
                assertEquals(reference.verifyContents(), measured.verifyContents());
            }
        }
    }

    @Test
    void pacedChurnAllocatesAndRetainsOnlyItsBoundedRing() {
        try (ApplicationChurn churn = new ApplicationChurn(8 * 1024 * 1024, 1024, 16)) {
            churn.start();
            LockSupport.parkNanos(250_000_000);
            ApplicationChurn.Snapshot first = churn.stop();
            assertTrue(first.allocatedBytes() > 0);
            assertTrue(first.jvmAllocatedBytes() >= first.allocatedBytes(), "JVM allocation counter must corroborate payload demand");
            assertEquals(16 * 1024, first.retainedPayloadBytes());
            assertTrue(first.realizedBytesPerSecond() > 0);
            churn.start();
            LockSupport.parkNanos(50_000_000);
            assertTrue(churn.stop().allocatedBytes() > 0);
        }
    }

    @Test
    void boundedBatchStopJoinsTheWorkerAndAllowsCleanSubsequentWindows() {
        try (ApplicationChurn churn = new ApplicationChurn(32 * 1024 * 1024, 4096, 8)) {
            for (int window = 0; window < 4; window++) {
                churn.start();
                LockSupport.parkNanos(40_000_000);
                ApplicationChurn.Snapshot snapshot = churn.stop();
                assertTrue(snapshot.endNs() > snapshot.startNs());
                assertTrue(snapshot.allocatedBytes() > 0);
                assertEquals(0, snapshot.allocatedBytes() % 4096);
                assertTrue(snapshot.jvmAllocatedBytes() >= snapshot.allocatedBytes());
                assertEquals(8 * 4096, snapshot.retainedPayloadBytes());
                assertThrows(IllegalStateException.class, churn::stop);
                assertTrue(Thread.getAllStackTraces().keySet().stream().noneMatch(
                        t -> t.isAlive() && t.getName().equals("tailcache-application-churn")),
                        "Stop must join its allocation worker before returning");
            }
        }
    }
}

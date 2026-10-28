package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CrossoverLatencyRunnerTest {
    @Test
    void workerPreservesTraceConsumptionAndRecordingAcrossFreshPhaseRecorders() {
        for (CrossoverBackend backend : CrossoverBackend.values()) {
            CrossoverConfig config = new CrossoverConfig(64, 256, 24301, 0, 4096, 0, 128);
            try (CrossoverWorkload actual = new CrossoverWorkload(backend, config);
                 CrossoverWorkload reference = new CrossoverWorkload(backend, config)) {
                // Exercise successive warmup/measurement-style calls with distinct recorders.
                for (int phase = 0; phase < 2; phase++) {
                    EveryOperationRecorder recorder = new EveryOperationRecorder();
                    actual.resetTraceCursor();
                    reference.resetTraceCursor();
                    long before = actual.operations();
                    long start = System.nanoTime();
                    var window = CrossoverLatencyRunner.runWindow(actual, recorder, start,
                            start + 2_000_000, false, false);
                    long operations = actual.operations() - before;
                    assertTrue(operations > 0);
                    assertTrue(window.endNs() >= start);
                    assertEquals(operations, recorder.operations());
                    assertEquals(operations, recorder.recordedCount());
                    assertEquals(0, recorder.overflowCount());
                    long expectedChecksum = 0;
                    for (long i = 0; i < operations; i++) expectedChecksum += reference.executeNext()[0];
                    assertEquals(expectedChecksum, window.checksum());
                    assertEquals(reference.writes(), actual.writes());
                    assertEquals(reference.verifyContents(), actual.verifyContents());
                }
            }
        }
    }
}

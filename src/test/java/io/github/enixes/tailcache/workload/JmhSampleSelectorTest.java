package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.*;

class JmhSampleSelectorTest {
    public static class HarnessMarker {
        public static final String TAILCACHE_SAMPLE_SELECTION_VERSION = JmhSampleSelector.VERSION;
    }

    @Test
    void actualSelectorPassesPredeclaredPeriodicControlAndWiderMask() {
        for (int mask : new int[]{15, 255, 1023}) {
            int phases = 512;
            int operations = 65536 * (mask + 1);
            for (int initial : new int[]{0, 1, -1}) {
                int[] counts = new int[phases];
                int rnd = initial, total = 0;
                for (int operation = 0; operation < operations; operation++) {
                    rnd = rnd * 1664525 + 1013904223;
                    if (JmhSampleSelector.select(rnd, mask)) {
                        counts[operation % phases]++;
                        total++;
                    }
                }
                for (int count : counts) assertTrue(count >= 64 && count <= 192);
                double expected = (double) operations / (mask + 1);
                assertTrue(Math.abs(total - expected) <= .01 * expected);
            }
        }
        for (int state : new int[]{0, 1, -1, Integer.MIN_VALUE, Integer.MAX_VALUE}) {
            assertTrue(JmhSampleSelector.select(state, 0));
            assertEquals(state == 0, JmhSampleSelector.select(state, -1));
        }
    }

    @Test
    void staleHarnessAndMissingControlFailAndActualClassBytesAreRetained(@TempDir Path directory) throws Exception {
        String previous = System.getProperty("tailcache12.sampleSelectionVersion");
        try {
            System.clearProperty("tailcache12.sampleSelectionVersion");
            assertThrows(IllegalStateException.class, () -> JmhSampleSelectionEvidence.write(directory, HarnessMarker.class));
            System.setProperty("tailcache12.sampleSelectionVersion", JmhSampleSelector.VERSION);
            assertThrows(IllegalStateException.class, () -> JmhSampleSelectionEvidence.write(directory, Object.class));
            JmhSampleSelectionEvidence.write(directory, HarnessMarker.class);
            long pid = ProcessHandle.current().pid();
            Path actual = directory.resolve("sample-harness-" + pid + ".class");
            byte[] bytes = Files.readAllBytes(actual);
            String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            assertTrue(Files.readString(directory.resolve("sample-selection-" + pid + ".properties"))
                    .contains("harnessSha256=" + hash));
            try (var resource = HarnessMarker.class.getResourceAsStream("/" + HarnessMarker.class.getName().replace('.', '/') + ".class")) {
                assertNotNull(resource);
                assertArrayEquals(resource.readAllBytes(), bytes);
            }
            assertThrows(IllegalStateException.class, () -> JmhSampleSelectionEvidence.write(directory, HarnessMarker.class));
        } finally {
            if (previous == null) System.clearProperty("tailcache12.sampleSelectionVersion");
            else System.setProperty("tailcache12.sampleSelectionVersion", previous);
        }
    }

    @Test
    void actualWorkerMarkerContainsJavaAndOsThreadIdentity(@TempDir Path directory) throws Exception {
        WorkerProcessEvidence.write(directory, CrossoverBackend.CAFFEINE, 256, "test");
        String marker = Files.readString(directory.resolve("worker-process-" + ProcessHandle.current().pid() + ".properties"));
        assertTrue(marker.contains("javaThreadId=" + Thread.currentThread().threadId() + "\n"));
        assertTrue(marker.contains("javaThreadName=" + Thread.currentThread().getName() + "\n"));
        assertTrue(marker.contains("osThreadId=" + Path.of("/proc/thread-self").toRealPath().getFileName() + "\n"));
    }
}

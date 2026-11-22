package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Files;
import java.nio.file.Path;
import static org.junit.jupiter.api.Assertions.*;

class DenseObserverCaptureTest {
    @Test void physicalWindowsConserveCountsAndExportAfterAllPhases(@TempDir Path root) throws Exception {
        var capture = new DenseObserverCapture(1,2,1);
        assertThrows(IllegalStateException.class, () -> capture.export(root.resolve("early")));
        for (int i=0; i<3; i++) {
            capture.resetIteration();capture.beginWindow(1000+i*1000);
            capture.record(1010+i*1000,1020+i*1000,1000+i*1000);
            capture.record(1030+i*1000,1040+i*1000,1020+i*1000);
            assertThrows(IllegalStateException.class, capture::resetIteration);
            assertThrows(IllegalStateException.class, () -> capture.finishWindow(3,1050));
            capture.finishWindow(2,1040+i*1000);
        }
        Path output=root.resolve("complete");capture.export(output);
        var rows=Files.readAllLines(output.resolve("iterations.csv"));
        assertEquals(4,rows.size());assertTrue(rows.get(1).startsWith("WARMUP,1,"));
        assertTrue(rows.get(2).startsWith("CONDITIONING,1,"));assertTrue(rows.get(3).startsWith("MEASUREMENT,1,"));
        for (String directory:new String[]{"","conditioning/"}) {
            var bins=Files.readAllLines(output.resolve(directory+"iteration-1-service-bins.csv"));
            assertEquals(2,bins.stream().skip(1).mapToLong(s -> Long.parseLong(s.split(",")[1])).sum());
            var decoded=org.HdrHistogram.Histogram.decodeFromCompressedByteBuffer(java.nio.ByteBuffer.wrap(
                    Files.readAllBytes(output.resolve(directory+"iteration-1-service.hdr"))),0);
            assertEquals(2,decoded.getTotalCount());
        }
        assertThrows(java.io.IOException.class, () -> capture.export(output));
        assertThrows(IllegalStateException.class, capture::resetIteration);
    }
}

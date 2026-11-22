package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class CrossoverConditioningTest {
    @TempDir Path temporary;

    @Test
    void conditioningAndAnalysisRetainSeparateCompleteHistograms() throws Exception {
        Path output = temporary.resolve("worker");
        CrossoverLatencyRunner.main(new String[]{"--out", output.toString(), "--backend", "CAFFEINE",
                "--residents", "32", "--payload", "256", "--churn-bytes-sec", "0",
                "--warmup", "1", "--conditioning", "2", "--measure", "2", "--iteration-ms", "10"});
        List<String> lines = Files.readAllLines(output.resolve("iterations.csv"));
        assertEquals(6, lines.size());
        List<String> header = List.of(lines.getFirst().split(","));
        int operations = header.indexOf("operations");
        assertTrue(Files.readString(output.resolve("configuration.txt")).contains("conditioningIterations=2\n"));
        assertEquals(List.of("WARMUP", "CONDITIONING", "CONDITIONING", "MEASUREMENT", "MEASUREMENT"),
                lines.subList(1, lines.size()).stream().map(line -> line.split(",")[0]).toList());
        for (String line : lines.subList(2, lines.size())) {
            String[] fields = line.split(",");
            Path directory = fields[0].equals("CONDITIONING") ? output.resolve("conditioning") : output;
            assertTrue(List.of("1", "2").contains(fields[1]));
            long completed = Long.parseLong(fields[operations]);
            assertTrue(completed > 0);
            for (String channel : List.of("service", "completion-gap")) {
                try (var rows = Files.lines(directory.resolve("iteration-" + fields[1] + "-" + channel + "-bins.csv"))) {
                    assertEquals(completed, rows.skip(1).mapToLong(row -> Long.parseLong(row.split(",")[1])).sum());
                }
            }
        }
        assertTrue(Files.exists(output.resolve("integrity.txt")));
    }
}

package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.profile.InternalProfiler;
import org.openjdk.jmh.results.IterationResult;
import org.openjdk.jmh.results.Result;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Collection;
import java.util.Collections;

/** Linux process counters around each JMH warmup and measurement iteration. */
public final class PilotOsCountersProfiler implements InternalProfiler {

    private final Path outputDirectory;
    private final long pid = ProcessHandle.current().pid();
    private Counters start;
    private long startNs;
    private int iteration;

    public PilotOsCountersProfiler() {
        this("");
    }

    public PilotOsCountersProfiler(String initLine) {
        if (initLine == null || !initLine.startsWith("dir=") || initLine.length() <= 4) {
            throw new IllegalArgumentException("Expected dir=<output directory>");
        }
        outputDirectory = Path.of(initLine.substring(4));
        try {
            Files.createDirectories(outputDirectory);
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to create profiler output directory", exception);
        }
    }

    @Override
    public String getDescription() {
        return "Linux minor/major faults and process I/O per JMH iteration (diagnostic)";
    }

    @Override
    public void beforeIteration(BenchmarkParams params, IterationParams iterationParams) {
        Path output = outputPath(params);
        if (iteration++ == 0) {
            try {
                Files.writeString(output,
                        "phase,sequence,envelopeNs,minorFaults,majorFaults,readBytes,writeBytes\n",
                        StandardCharsets.UTF_8, StandardOpenOption.CREATE,
                        StandardOpenOption.TRUNCATE_EXISTING);
            } catch (IOException exception) {
                throw new IllegalStateException("Unable to initialize " + output, exception);
            }
        }
        start = Counters.read();
        startNs = System.nanoTime();
    }

    @Override
    public Collection<? extends Result> afterIteration(
            BenchmarkParams params, IterationParams iterationParams, IterationResult result
    ) {
        long elapsed = System.nanoTime() - startNs;
        Counters end = Counters.read();
        String row = iterationParams.getType() + "," + iteration + "," + elapsed + ","
                + (end.minorFaults - start.minorFaults) + ","
                + (end.majorFaults - start.majorFaults) + ","
                + (end.readBytes - start.readBytes) + ","
                + (end.writeBytes - start.writeBytes) + "\n";
        try {
            Files.writeString(outputPath(params), row, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException exception) {
            throw new IllegalStateException("Unable to write pilot OS counters", exception);
        }
        return Collections.emptyList();
    }

    private Path outputPath(BenchmarkParams params) {
        Path windows = GcProfileFiles.measurementWindows(outputDirectory, params, pid);
        return windows.resolveSibling(windows.getFileName().toString().replace(".windows.csv", ".os.csv"));
    }

    private record Counters(long minorFaults, long majorFaults, long readBytes, long writeBytes) {
        static Counters read() {
            try {
                String stat = Files.readString(Path.of("/proc/self/stat"));
                // The command name in parentheses can contain spaces or closing parentheses.
                String[] fields = stat.substring(stat.lastIndexOf(')') + 2).trim().split("\\s+");
                long minor = Long.parseLong(fields[7]);  // Linux stat field 10
                long major = Long.parseLong(fields[9]);  // Linux stat field 12
                long read = 0;
                long written = 0;
                for (String line : Files.readAllLines(Path.of("/proc/self/io"))) {
                    if (line.startsWith("read_bytes:")) {
                        read = Long.parseLong(line.substring(11).trim());
                    } else if (line.startsWith("write_bytes:")) {
                        written = Long.parseLong(line.substring(12).trim());
                    }
                }
                return new Counters(minor, major, read, written);
            } catch (IOException exception) {
                throw new IllegalStateException("Linux /proc counters unavailable", exception);
            }
        }
    }
}

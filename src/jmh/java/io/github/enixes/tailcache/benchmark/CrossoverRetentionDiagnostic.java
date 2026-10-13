package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.workload.*;

import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;

/** Full-GC/class-histogram retention diagnostic, never a timed campaign path. */
public final class CrossoverRetentionDiagnostic {
    private CrossoverRetentionDiagnostic() { }

    public static void main(String[] args) throws Exception {
        if (args.length != 4) throw new IllegalArgumentException("Expected backend residents payload output-directory");
        CrossoverBackend backend = CrossoverBackend.valueOf(args[0]);
        int residents = Integer.parseInt(args[1]);
        int payload = Integer.parseInt(args[2]);
        Path directory = Path.of(args[3]);
        if (Files.exists(directory)) throw new IllegalStateException("Output exists: " + directory);
        Files.createDirectories(directory);
        histogram(directory.resolve("empty.txt"));
        CrossoverConfig config = new CrossoverConfig(residents, payload, 0x5EEDL, 0, 4096, 0, 128);
        try (CrossoverWorkload workload = new CrossoverWorkload(backend, config)) {
            histogram(directory.resolve("populated.txt"));
            Files.writeString(directory.resolve("observation.txt"), "backend=" + backend + "\nresidents=" + residents
                    + "\npayload=" + payload + "\nchecksum=" + workload.verifyContents() + "\nsize=" + workload.size()
                    + "\nconfig=" + workload.backendConfiguration() + "\nheapUsed="
                    + ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed() + "\n");
            java.lang.ref.Reference.reachabilityFence(workload);
        }
    }

    private static void histogram(Path output) throws Exception {
        Path jcmd = Path.of(System.getProperty("java.home"), "bin", "jcmd");
        Process process = new ProcessBuilder(jcmd.toString(), Long.toString(ProcessHandle.current().pid()),
                "GC.class_histogram").redirectErrorStream(true).redirectOutput(output.toFile()).start();
        if (!process.waitFor(30, java.util.concurrent.TimeUnit.SECONDS)) {
            process.destroyForcibly();
            throw new IllegalStateException("Class histogram timed out");
        }
        if (process.exitValue() != 0) throw new IllegalStateException("Class histogram failed: " + output);
    }
}

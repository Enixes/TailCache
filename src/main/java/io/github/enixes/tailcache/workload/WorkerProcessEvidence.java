package io.github.enixes.tailcache.workload;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Setup-only proof that the actual worker belongs to the accounted native scope. */
public final class WorkerProcessEvidence {
    private WorkerProcessEvidence() { }

    public static void write(Path directory, CrossoverBackend backend, int payloadBytes, String mode) {
        try {
            String group = Files.readAllLines(Path.of("/proc/self/cgroup")).stream()
                    .filter(line -> line.startsWith("0::/"))
                    .map(line -> line.substring(3)).findFirst().orElse("unavailable");
            String expected = System.getenv("TAILCACHE_NATIVE_SCOPE");
            if ("1".equals(System.getenv("TAILCACHE_REQUIRE_NATIVE_HOST"))
                    && (expected == null || !expected.matches("tailcache12-[A-Za-z0-9._-]+\\.scope")
                    || !group.endsWith("/" + expected))) {
                throw new IllegalStateException("Worker escaped its declared native accounting scope: " + group);
            }
            long pid = ProcessHandle.current().pid();
            Thread worker = Thread.currentThread();
            String osThreadId = Path.of("/proc/thread-self").toRealPath().getFileName().toString();
            WorkerAllocationCounter.currentBytes();
            Files.writeString(directory.resolve("worker-process-" + pid + ".properties"),
                    "pid=" + pid + "\ncgroup=" + group + "\nbackend=" + backend
                            + "\npayloadBytes=" + payloadBytes + "\nmode=" + mode
                            + "\njavaThreadId=" + worker.threadId() + "\nosThreadId=" + osThreadId
                            + "\njavaThreadName=" + worker.getName()
                            + "\nworkerAllocationCounters=true\n",
                    StandardOpenOption.CREATE_NEW);
        } catch (IOException failure) {
            throw new UncheckedIOException("Cannot retain worker process evidence", failure);
        }
    }
}

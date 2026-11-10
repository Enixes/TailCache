package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.cache.CacheAdapter;
import io.github.enixes.tailcache.cache.CacheConfig;
import io.github.enixes.tailcache.workload.AccessPattern;
import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.PayloadSize;
import io.github.enixes.tailcache.workload.ReadWriteMix;
import io.github.enixes.tailcache.workload.SyntheticKeyValueGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;
import io.github.enixes.tailcache.workload.WorkloadTrace;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;

import java.io.IOException;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

import static java.nio.file.StandardOpenOption.READ;

/**
 * Shared cache state for TailCache's mixed-workload matrix.
 *
 * <p>This state deliberately uses {@link Scope#Benchmark}: every JMH worker in a multi-threaded run
 * accesses the same cache instance. Per-thread trace cursors live in {@link WorkloadCursorState}, so
 * increasing {@code -t} models same-JVM shared-cache contention rather than silently constructing
 * one independent cache per worker.</p>
 */
@State(Scope.Benchmark)
public class CacheWorkloadState {

    static final int CAPACITY = 4_096;
    static final int KEY_SPACE = 2_048;
    static final int TRACE_SIZE = 100_000;
    static final long WORKLOAD_SEED = 0x5EEDL;

    @Param({"CAFFEINE", "CHRONICLE_IN_MEMORY", "CHRONICLE_PERSISTED"})
    public BenchmarkBackendMode mode;

    @Param({"BYTES_256", "KIB_4"})
    public PayloadSize payloadSize;

    @Param({"UNIFORM", "ZIPFIAN"})
    public AccessPattern accessPattern;

    @Param({"READ_95_WRITE_5", "READ_70_WRITE_30"})
    public ReadWriteMix readWriteMix;

    private CacheAdapter cache;
    private WorkloadTrace trace;
    private Long[] keys;
    private byte[][] replacementValues;
    private Path persistedDirectory;
    private Path persistedFile;
    private MappedByteBuffer prefaultMapping;
    private volatile long prefaultChecksum;

    @Setup(Level.Trial)
    public void setupTrial() throws IOException {
        if (!Boolean.getBoolean("chronicle.analytics.disable")) {
            throw new IllegalStateException("Benchmark fork must disable Chronicle analytics");
        }
        SyntheticKeyValueGenerator dataGenerator = new SyntheticKeyValueGenerator();
        CacheConfig cacheConfig = new CacheConfig(CAPACITY, payloadSize.bytes());

        if (mode.isPersisted()) {
            Path root = Path.of(System.getProperty(
                    "tailcache.persistedRoot", System.getProperty("java.io.tmpdir")
            )).toAbsolutePath();
            Files.createDirectories(root);
            persistedDirectory = Files.createTempDirectory(root, "tailcache-chronicle-");
            persistedFile = persistedDirectory.resolve("tailcache.map");
        }

        cache = mode.create(cacheConfig, persistedFile);
        keys = new Long[KEY_SPACE];
        replacementValues = new byte[KEY_SPACE][];

        for (int index = 0; index < KEY_SPACE; index++) {
            Long key = dataGenerator.keyForIndex(index);
            keys[index] = key;
            cache.put(key, dataGenerator.valueFor(key, payloadSize));

            long replacementSeedKey = dataGenerator.keyForIndex(KEY_SPACE * 2 + index);
            replacementValues[index] = dataGenerator.valueFor(replacementSeedKey, payloadSize);
        }

        WorkloadSpec workloadSpec = switch (accessPattern) {
            case UNIFORM -> WorkloadSpec.uniform(
                    TRACE_SIZE, KEY_SPACE, readWriteMix.readRatio(), WORKLOAD_SEED
            );
            case ZIPFIAN -> WorkloadSpec.zipfian(
                    TRACE_SIZE, KEY_SPACE, readWriteMix.readRatio(), WORKLOAD_SEED
            );
            case HOTSPOT -> WorkloadSpec.hotspot(
                    TRACE_SIZE, KEY_SPACE, readWriteMix.readRatio(), WORKLOAD_SEED, 0.2, 0.8
            );
        };
        trace = new DeterministicWorkloadGenerator().generate(workloadSpec);

        if (cache.size() != KEY_SPACE) {
            throw new IllegalStateException(
                    "Expected " + KEY_SPACE + " entries after setup, found " + cache.size()
            );
        }

        byte[] expectedFirstHit = dataGenerator.valueFor(keys[0], payloadSize);
        if (!Arrays.equals(expectedFirstHit, cache.get(keys[0]))) {
            throw new IllegalStateException("Cache hit sanity check failed during workload setup");
        }

        if (persistedFile != null) {
            // Warm the file's page cache, then touch Chronicle's own mapped entry pages via get().
            // This reduces first-touch bias but cannot prevent later eviction under host pressure.
            try (FileChannel channel = FileChannel.open(persistedFile, READ)) {
                long size = channel.size();
                if (size > Integer.MAX_VALUE) {
                    throw new IllegalStateException("Pilot prefault supports files up to 2 GiB: " + size);
                }
                prefaultMapping = channel.map(FileChannel.MapMode.READ_ONLY, 0, size);
                prefaultMapping.load();
            }
            prefaultEntries();
        }

        String zipfExponent = accessPattern == AccessPattern.ZIPFIAN
                ? Double.toString(workloadSpec.zipfExponent())
                : "n/a";

        System.out.printf(
                "[TailCache][workload-config] mode=%s adapter=%s backendConfig={%s} "
                        + "stateScope=Benchmark(shared-cache) configuredEntries=%d populatedEntries=%d "
                        + "payloadBytes=%d traceSize=%d workloadSeed=0x%X accessPattern=%s "
                        + "zipfExponent=%s readRatio=%.2f writeRatio=%.2f keyRepresentation=preboxed-Long "
                        + "analyticsDisabled=%s persistedTempFile=%s persistedFileBytes=%s "
                        + "persistedFileStore=%s prefault=%s%n",
                mode,
                cache.name(),
                cache.configurationSummary(),
                CAPACITY,
                KEY_SPACE,
                payloadSize.bytes(),
                TRACE_SIZE,
                WORKLOAD_SEED,
                accessPattern,
                zipfExponent,
                readWriteMix.readRatio(),
                readWriteMix.writeRatio(),
                Boolean.getBoolean("chronicle.analytics.disable"),
                persistedFile == null ? "n/a" : persistedFile,
                persistedFile == null ? "n/a" : Files.size(persistedFile),
                persistedFile == null ? "n/a" : Files.getFileStore(persistedFile),
                persistedFile == null ? "n/a" : "trialEntrySweep+mappedPageTouchEachIteration"
        );
    }

    @Setup(Level.Iteration)
    public void setupIteration() {
        if (persistedFile != null) {
            prefaultMappedPages();
        }
    }

    private void prefaultMappedPages() {
        // Page-cache touch with no per-entry byte[] materialization before the timed interval.
        MappedByteBuffer pages = prefaultMapping;
        pages.load();
        long checksum = 0;
        for (int offset = 0; offset < pages.limit(); offset += 4_096) {
            checksum += pages.get(offset);
        }
        checksum += pages.get(pages.limit() - 1);
        prefaultChecksum = checksum;
    }

    private void prefaultEntries() {
        long checksum = 0;
        for (Long key : keys) {
            byte[] value = cache.get(key);
            if (value == null || value.length != payloadSize.bytes()) {
                throw new IllegalStateException("Prefault entry missing or wrong size: " + key);
            }
            checksum += value[0] + value[value.length - 1];
        }
        prefaultChecksum = checksum;
    }

    @TearDown(Level.Trial)
    public void tearDownTrial() throws IOException {
        RuntimeException observationFailure = null;
        try {
            if (cache != null && keys != null) {
                int updatedEntries = 0;
                for (int index = 0; index < keys.length; index++) {
                    if (Arrays.equals(cache.get(keys[index]), replacementValues[index])) {
                        updatedEntries++;
                    }
                }
                System.out.printf("[TailCache][workload-observation] mode=%s payloadBytes=%d "
                                + "updatedEntries=%d prefaultChecksum=%d%n",
                        mode, payloadSize.bytes(), updatedEntries, prefaultChecksum);
            }
        } catch (RuntimeException exception) {
            observationFailure = exception;
        }
        prefaultMapping = null;
        RuntimeException closeFailure = null;
        if (cache != null) {
            try {
                cache.close();
            } catch (RuntimeException exception) {
                closeFailure = exception;
            }
        }

        IOException cleanupFailure = null;
        if (persistedFile != null) {
            try {
                Files.deleteIfExists(persistedFile);
            } catch (IOException exception) {
                cleanupFailure = exception;
            }
        }
        if (persistedDirectory != null) {
            try {
                Files.deleteIfExists(persistedDirectory);
            } catch (IOException exception) {
                if (cleanupFailure == null) {
                    cleanupFailure = exception;
                } else {
                    cleanupFailure.addSuppressed(exception);
                }
            }
        }

        if (observationFailure != null) {
            if (closeFailure != null) {
                observationFailure.addSuppressed(closeFailure);
            }
            if (cleanupFailure != null) {
                observationFailure.addSuppressed(cleanupFailure);
            }
            throw observationFailure;
        }
        if (closeFailure != null) {
            if (cleanupFailure != null) {
                closeFailure.addSuppressed(cleanupFailure);
            }
            throw closeFailure;
        }
        if (cleanupFailure != null) {
            throw cleanupFailure;
        }
    }

    public CacheAdapter cache() {
        return cache;
    }

    public int traceSize() {
        return trace.size();
    }

    public boolean isReadAt(int traceIndex) {
        return trace.isReadAt(traceIndex);
    }

    public int logicalIndexAt(int traceIndex) {
        return Math.toIntExact(trace.keyAt(traceIndex));
    }

    public Long keyForLogicalIndex(int logicalIndex) {
        return keys[logicalIndex];
    }

    public byte[] replacementValueForLogicalIndex(int logicalIndex) {
        return replacementValues[logicalIndex];
    }
}

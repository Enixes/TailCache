package io.github.enixes.tailcache.workload;

import io.github.enixes.tailcache.cache.CacheAdapter;
import io.github.enixes.tailcache.cache.CaffeineCacheAdapter;

import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.HexFormat;

/** Single cache worker shared by JMH and every-operation channels; no retained payload bank. */
public final class CrossoverWorkload implements AutoCloseable {
    // JMH SampleTime selects low LCG bits with a power-of-two mask. An even
    // period permanently excludes trace phases within each fixed-mask segment.
    public static final int TRACE_SIZE = 40_001;
    public static final int TRACE_READ_COUNT = (int) Math.round(TRACE_SIZE * 0.95);
    public static final int TRACE_WRITE_COUNT = TRACE_SIZE - TRACE_READ_COUNT;
    public static final String TRACE_PERIOD_VERSION = "odd-period-v1";
    private final CrossoverConfig config;
    private final CacheAdapter cache;
    private final Long[] keys;
    private final long[] versions;
    private final WorkloadTrace trace;
    private final FreshValueGenerator values = new FreshValueGenerator();
    private final RetainedApplicationData applicationData;
    private int cursor;
    private long writes;
    private long operations;
    private boolean closed;

    public CrossoverWorkload(CrossoverBackend backend, CrossoverConfig config) {
        this(backend, config, TRACE_SIZE);
    }

    /** Separate follow-up cohorts can freeze a longer trace without changing legacy defaults. */
    public CrossoverWorkload(CrossoverBackend backend, CrossoverConfig config, int traceSize) {
        if (traceSize < 1 || traceSize > 2_000_003) throw new IllegalArgumentException("Invalid trace size");
        this.config = config;
        if (!Boolean.getBoolean("chronicle.analytics.disable")) {
            throw new IllegalStateException("Chronicle analytics must be disabled");
        }
        cache = backend.create(config);
        try {
            keys = new Long[config.residentEntries()];
            versions = new long[keys.length];
            SyntheticKeyValueGenerator keyGenerator = new SyntheticKeyValueGenerator();
            for (int i = 0; i < keys.length; i++) {
                keys[i] = keyGenerator.keyForIndex(i);
                cache.put(keys[i], values.create(keys[i], 0, config.payloadBytes()));
            }
            trace = new DeterministicWorkloadGenerator().generate(
                    WorkloadSpec.uniform(traceSize, keys.length, 0.95, config.seed()));
            applicationData = new RetainedApplicationData(
                    config.applicationLiveBytes(), config.applicationObjectBytes());
            verifyContents();
            if (cache instanceof CaffeineCacheAdapter caffeine && caffeine.isBoundedForDiagnostic() && caffeine.frequencySketchSlotsForDiagnostic() == 0) {
                throw new IllegalStateException("Crossover Caffeine frequency sketch is not initialized");
            }
        } catch (RuntimeException | Error failure) {
            cache.close();
            throw failure;
        }
    }

    /** Fresh generation is inside the measured update boundary; callers consume the result. */
    public byte[] executeNext() {
        int position = cursor++;
        if (cursor == trace.size()) cursor = 0;
        int index = (int) trace.keyAt(position);
        Long key = keys[index];
        operations++;
        if (trace.isReadAt(position)) {
            byte[] value = cache.get(key);
            if (value == null) throw new IllegalStateException("Unexpected cache miss");
            return value;
        }
        long version = writes + 1;
        byte[] fresh = values.create(key, version, config.payloadBytes());
        cache.put(key, fresh);
        versions[index] = version;
        writes = version;
        return fresh;
    }

    public void resetTraceCursor() { cursor = 0; }

    /** Secondary borrowed-buffer read contract, with identical trace/fresh immutable writes. */
    public byte[] executeNextUsing(byte[] using) {
        int position = cursor++;
        if (cursor == trace.size()) cursor = 0;
        int index = (int) trace.keyAt(position);
        Long key = keys[index];
        operations++;
        if (trace.isReadAt(position)) {
            byte[] value = ((io.github.enixes.tailcache.cache.ChronicleMapCacheAdapter) cache).getUsing(key, using);
            if (value == null) throw new IllegalStateException("Unexpected cache miss");
            if (value != using) throw new IllegalStateException("Requested buffer was not reused");
            return value;
        }
        long version = writes + 1;
        byte[] fresh = values.create(key, version, config.payloadBytes());
        cache.put(key, fresh);
        versions[index] = version;
        writes = version;
        return fresh;
    }

    /** Trace/branch/fresh-supply floor. No cache access and no mutation of stored versions. */
    public Object executeSupplyFloorNext() {
        int position = cursor++;
        if (cursor == trace.size()) cursor = 0;
        int index = (int) trace.keyAt(position);
        operations++;
        return trace.isReadAt(position) ? keys[index]
                : values.create(keys[index], ++writes, config.payloadBytes());
    }
    public long operations() { return operations; }
    public long writes() { return writes; }
    public long reads() { return operations - writes; }
    /** Setup-only allocation; these key-coverage arrays are not retained by the workload. */
    public String traceConfiguration() {
        boolean[] accessed = new boolean[keys.length], read = new boolean[keys.length], updated = new boolean[keys.length];
        int readOperations = 0;
        for (int i = 0; i < trace.size(); i++) {
            int key = (int) trace.keyAt(i);
            accessed[key] = true;
            if (trace.isReadAt(i)) { read[key] = true; readOperations++; } else updated[key] = true;
        }
        int all = 0, reads = 0, writes = 0;
        for (int i = 0; i < keys.length; i++) {
            if (accessed[i]) all++;
            if (read[i]) reads++;
            if (updated[i]) writes++;
        }
        return "traceOperations=" + trace.size() + "\ntraceReadOperations=" + readOperations
                + "\ntraceWriteOperations=" + (trace.size() - readOperations)
                + "\ntraceDistinctKeys=" + all + "\ntraceDistinctReadKeys=" + reads
                + "\ntraceDistinctWriteKeys=" + writes + "\ntraceArrayPayloadBytes=" + (9L * trace.size());
    }
    public long size() { return cache.size(); }
    public long applicationChecksum() { return applicationData.checksum(); }
    public String backendConfiguration() {
        return cache.configurationSummary() + (cache instanceof CaffeineCacheAdapter caffeine
                ? ",frequencySketchSlots=" + caffeine.frequencySketchSlotsForDiagnostic() : "");
    }

    /** Allocating diagnostic, outside measurement; checks every key and version. */
    public long verifyContents() {
        if (cache.size() != config.residentEntries()) throw new IllegalStateException("Resident count changed");
        long checksum = 0;
        for (int i = 0; i < keys.length; i++) {
            byte[] actual = cache.get(keys[i]);
            byte[] expected = values.create(keys[i], versions[i], config.payloadBytes());
            if (!Arrays.equals(actual, expected)) throw new IllegalStateException("Wrong value for logical key " + i);
            checksum += actual[0] + actual[actual.length - 1];
        }
        return checksum;
    }

    public String traceFingerprint() {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            ByteBuffer key = ByteBuffer.allocate(Long.BYTES);
            for (int i = 0; i < trace.size(); i++) {
                key.clear();
                key.putLong(trace.keyAt(i));
                digest.update(key.array());
                digest.update((byte) (trace.isReadAt(i) ? 1 : 0));
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException exception) {
            throw new AssertionError(exception);
        }
    }

    @Override
    public void close() {
        if (!closed) {
            closed = true;
            cache.close();
        }
    }
}

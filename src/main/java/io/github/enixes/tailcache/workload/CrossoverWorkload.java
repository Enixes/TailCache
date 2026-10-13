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
    public static final int TRACE_SIZE = 40_000;
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
                    WorkloadSpec.uniform(TRACE_SIZE, keys.length, 0.95, config.seed()));
            applicationData = new RetainedApplicationData(
                    config.applicationLiveBytes(), config.applicationObjectBytes());
            verifyContents();
            if (cache instanceof CaffeineCacheAdapter caffeine && caffeine.frequencySketchSlotsForDiagnostic() == 0) {
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

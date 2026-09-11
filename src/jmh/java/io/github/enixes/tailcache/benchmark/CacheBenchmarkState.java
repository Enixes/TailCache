package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.cache.CacheAdapter;
import io.github.enixes.tailcache.cache.CacheBackend;
import io.github.enixes.tailcache.cache.CacheConfig;
import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.PayloadSize;
import io.github.enixes.tailcache.workload.SyntheticKeyValueGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;
import io.github.enixes.tailcache.workload.WorkloadTrace;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;

import java.util.Arrays;

/**
 * Shared state for cache microbenchmarks.
 *
 * All expensive or unrelated work happens in setup: cache construction,
 * payload allocation, key generation and workload generation. Benchmark
 * methods only select a pre-generated key and call the cache API.
 */
@State(Scope.Thread)
public class CacheBenchmarkState {

    static final int CAPACITY = 4_096;
    static final int KEY_SPACE = 2_048;
    static final int TRACE_SIZE = 100_000;
    static final long WORKLOAD_SEED = 0x5EEDL;

    @Param({"CAFFEINE", "CHRONICLE_MAP"})
    public CacheBackend backend;

    @Param({"BYTES_256", "KIB_4"})
    public PayloadSize payloadSize;

    private CacheAdapter cache;
    private WorkloadTrace trace;
    private Long[] hitKeys;
    private Long[] missKeys;
    private byte[] overwriteValue;
    private int cursor;

    @Setup(Level.Trial)
    public void setupTrial() {
        SyntheticKeyValueGenerator dataGenerator = new SyntheticKeyValueGenerator();
        CacheConfig cacheConfig = new CacheConfig(CAPACITY, payloadSize.bytes());

        cache = backend.create(cacheConfig);
        hitKeys = new Long[KEY_SPACE];
        missKeys = new Long[KEY_SPACE];

        for (int index = 0; index < KEY_SPACE; index++) {
            Long hitKey = dataGenerator.keyForIndex(index);
            Long missKey = dataGenerator.keyForIndex(KEY_SPACE + index);

            hitKeys[index] = hitKey;
            missKeys[index] = missKey;
            cache.put(hitKey, dataGenerator.valueFor(hitKey, payloadSize));
        }

        trace = new DeterministicWorkloadGenerator().generate(
                WorkloadSpec.uniform(TRACE_SIZE, KEY_SPACE, 1.0, WORKLOAD_SEED)
        );

        Long overwriteKey = dataGenerator.keyForIndex(KEY_SPACE * 2);
        overwriteValue = dataGenerator.valueFor(overwriteKey, payloadSize);

        if (cache.size() != KEY_SPACE) {
            throw new IllegalStateException(
                    "Expected " + KEY_SPACE + " entries after setup, found " + cache.size()
            );
        }

        byte[] expectedFirstHit = dataGenerator.valueFor(hitKeys[0], payloadSize);
        if (!Arrays.equals(expectedFirstHit, cache.get(hitKeys[0]))) {
            throw new IllegalStateException("Cache hit sanity check failed during trial setup");
        }
        if (cache.get(missKeys[0]) != null) {
            throw new IllegalStateException("Cache miss sanity check failed during trial setup");
        }

        System.out.printf(
                "[TailCache][config] backend=%s adapter=%s backendConfig={%s} capacity=%d populatedEntries=%d payloadBytes=%d traceSize=%d workloadSeed=0x%X keyRepresentation=preboxed-Long%n",
                backend,
                cache.name(),
                cache.configurationSummary(),
                CAPACITY,
                KEY_SPACE,
                payloadSize.bytes(),
                TRACE_SIZE,
                WORKLOAD_SEED
        );
    }

    @Setup(Level.Iteration)
    public void setupIteration() {
        cursor = 0;
    }

    @TearDown(Level.Trial)
    public void tearDownTrial() {
        if (cache != null) {
            cache.close();
        }
    }

    public CacheAdapter cache() {
        return cache;
    }

    public Long nextHitKey() {
        return hitKeys[nextLogicalIndex()];
    }

    public Long nextMissKey() {
        return missKeys[nextLogicalIndex()];
    }

    public byte[] overwriteValue() {
        return overwriteValue;
    }

    private int nextLogicalIndex() {
        int traceIndex = cursor++;
        if (cursor == trace.size()) {
            cursor = 0;
        }
        return Math.toIntExact(trace.keyAt(traceIndex));
    }
}

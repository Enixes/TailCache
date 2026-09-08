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
    private long[] hitKeys;
    private long[] missKeys;
    private byte[] overwriteValue;
    private int cursor;

    @Setup(Level.Trial)
    public void setupTrial() {
        SyntheticKeyValueGenerator dataGenerator = new SyntheticKeyValueGenerator();

        cache = backend.create(new CacheConfig(CAPACITY, payloadSize.bytes()));
        hitKeys = new long[KEY_SPACE];
        missKeys = new long[KEY_SPACE];

        for (int index = 0; index < KEY_SPACE; index++) {
            long hitKey = dataGenerator.keyForIndex(index);
            long missKey = dataGenerator.keyForIndex(KEY_SPACE + index);

            hitKeys[index] = hitKey;
            missKeys[index] = missKey;
            cache.put(hitKey, dataGenerator.valueFor(hitKey, payloadSize));
        }

        trace = new DeterministicWorkloadGenerator().generate(
                WorkloadSpec.uniform(TRACE_SIZE, KEY_SPACE, 1.0, WORKLOAD_SEED)
        );

        long overwriteKey = dataGenerator.keyForIndex(KEY_SPACE * 2);
        overwriteValue = dataGenerator.valueFor(overwriteKey, payloadSize);

        if (cache.size() != KEY_SPACE) {
            throw new IllegalStateException(
                    "Expected " + KEY_SPACE + " entries after setup, found " + cache.size()
            );
        }
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

    public long nextHitKey() {
        return hitKeys[nextLogicalIndex()];
    }

    public long nextMissKey() {
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

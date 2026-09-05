package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.cache.CacheAdapter;
import io.github.enixes.tailcache.cache.CacheBackend;
import io.github.enixes.tailcache.cache.CacheConfig;
import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;
import io.github.enixes.tailcache.workload.WorkloadTrace;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Warmup;

import java.util.concurrent.TimeUnit;

/**
 * Harness smoke test only. The iteration lengths are intentionally not suitable for publication.
 */
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 1, time = 300, timeUnit = TimeUnit.MILLISECONDS)
@Measurement(iterations = 1, time = 300, timeUnit = TimeUnit.MILLISECONDS)
@Fork(
        value = 1,
        jvmArgsAppend = {
                "--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED",
                "--add-exports=java.base/jdk.internal.ref=ALL-UNNAMED",
                "--add-exports=java.base/jdk.internal.util=ALL-UNNAMED",
                "--add-exports=java.base/sun.nio.ch=ALL-UNNAMED",
                "--add-exports=jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED",
                "--add-exports=jdk.unsupported/sun.misc=ALL-UNNAMED",
                "--add-opens=java.base/java.io=ALL-UNNAMED",
                "--add-opens=java.base/java.lang=ALL-UNNAMED",
                "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
                "--add-opens=java.base/java.util=ALL-UNNAMED",
                "--add-opens=jdk.compiler/com.sun.tools.javac=ALL-UNNAMED"
        }
)
public class CacheSmokeBenchmark {

    @State(Scope.Thread)
    public static class BenchmarkState {

        private static final int CAPACITY = 4_096;
        private static final int KEY_SPACE = 2_048;
        private static final int VALUE_SIZE = 256;
        private static final int TRACE_SIZE = 100_000;

        @Param({"CAFFEINE", "CHRONICLE_MAP"})
        public String backend;

        CacheAdapter cache;
        WorkloadTrace trace;
        byte[] overwriteValue;
        int cursor;

        @Setup(Level.Trial)
        public void setup() {
            cache = CacheBackend.valueOf(backend).create(new CacheConfig(CAPACITY, VALUE_SIZE));

            for (long key = 0; key < KEY_SPACE; key++) {
                cache.put(key, valueFor(key, VALUE_SIZE));
            }

            trace = new DeterministicWorkloadGenerator().generate(
                    WorkloadSpec.uniform(TRACE_SIZE, KEY_SPACE, 1.0, 0x5EEDL)
            );
            overwriteValue = valueFor(-1, VALUE_SIZE);
            cursor = 0;
        }

        @TearDown(Level.Trial)
        public void tearDown() {
            cache.close();
        }

        long nextHitKey() {
            int index = cursor++;
            if (cursor == trace.size()) {
                cursor = 0;
            }
            return trace.keyAt(index);
        }

        private static byte[] valueFor(long key, int size) {
            byte[] value = new byte[size];
            long state = key ^ 0x9E3779B97F4A7C15L;
            for (int i = 0; i < value.length; i++) {
                state ^= state << 13;
                state ^= state >>> 7;
                state ^= state << 17;
                value[i] = (byte) state;
            }
            return value;
        }
    }

    @Benchmark
    public byte[] getHit(BenchmarkState state) {
        return state.cache.get(state.nextHitKey());
    }

    @Benchmark
    public byte[] getMiss(BenchmarkState state) {
        return state.cache.get(state.nextHitKey() + 1_000_000L);
    }

    @Benchmark
    public byte[] putExisting(BenchmarkState state) {
        long key = state.nextHitKey();
        state.cache.put(key, state.overwriteValue);
        return state.overwriteValue;
    }
}

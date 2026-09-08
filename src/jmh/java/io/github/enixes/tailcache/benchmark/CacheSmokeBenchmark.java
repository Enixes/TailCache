package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Warmup;

import java.util.concurrent.TimeUnit;

/**
 * Minimal cache-operation suite used to validate TailCache's JMH plumbing.
 *
 * The Gradle jmhSmoke task overrides these timings with a deliberately short
 * 1/1/1 run. The annotations below provide a more realistic default when the
 * benchmark is launched directly, but results are still not reportable until
 * the experiment protocol is frozen.
 */
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Measurement(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Fork(
        value = 3,
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

    @Benchmark
    public byte[] getHit(CacheBenchmarkState state) {
        return state.cache().get(state.nextHitKey());
    }

    @Benchmark
    public byte[] getMiss(CacheBenchmarkState state) {
        return state.cache().get(state.nextMissKey());
    }

    @Benchmark
    public byte[] putExisting(CacheBenchmarkState state) {
        byte[] value = state.overwriteValue();
        state.cache().put(state.nextHitKey(), value);
        return value;
    }
}

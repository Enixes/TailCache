package io.github.enixes.tailcache.benchmark;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Warmup;
import org.openjdk.jmh.infra.Blackhole;

import java.util.concurrent.TimeUnit;

/**
 * Minimal cache-operation suite used to validate TailCache's JMH plumbing.
 *
 * The Gradle jmhSmoke task overrides these timings with a deliberately short
 * 1/1/1 run. The annotations below provide a more realistic default when the
 * benchmark is launched directly, but results are still not reportable until
 * the experiment protocol is frozen.
 *
 * JVM module flags are configured on the Gradle JavaExec runner. JMH inherits
 * the runner's input arguments for forked VMs when benchmark-specific JVM args
 * are not supplied, avoiding duplicate --add-opens/--add-exports flags.
 */
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Measurement(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Fork(3)
public class CacheSmokeBenchmark {

    @Benchmark
    public void getHit(CacheBenchmarkState state, Blackhole blackhole) {
        blackhole.consume(state.cache().get(state.nextHitKey()));
    }

    @Benchmark
    public void getMiss(CacheBenchmarkState state, Blackhole blackhole) {
        blackhole.consume(state.cache().get(state.nextMissKey()));
    }

    @Benchmark
    public void putExisting(CacheBenchmarkState state) {
        state.cache().put(state.nextHitKey(), state.overwriteValue());
    }
}

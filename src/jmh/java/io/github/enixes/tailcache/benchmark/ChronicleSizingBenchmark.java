package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.workload.DeterministicWorkloadGenerator;
import io.github.enixes.tailcache.workload.WorkloadSpec;
import io.github.enixes.tailcache.workload.WorkloadTrace;
import net.openhft.chronicle.map.ChronicleMap;
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
import org.openjdk.jmh.infra.Blackhole;

import java.io.IOException;
import java.util.Arrays;
import java.util.concurrent.TimeUnit;

/** Steady-state in-memory sensitivity at 192 existing keys, below the capacity probe boundary. */
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 8, time = 1, timeUnit = TimeUnit.SECONDS)
@Measurement(iterations = 5, time = 1, timeUnit = TimeUnit.SECONDS)
@Fork(2)
public class ChronicleSizingBenchmark {
    @State(Scope.Thread)
    public static class SizingState {
        @Param({"192"})
        public int residentEntries;

        @Param({"256", "4096"})
        public int actualPayloadBytes;

        @Param({"HALF", "MATCH", "DOUBLE", "CONSTANT"})
        public ChronicleSizingConfig.Estimate estimate;

        private ChronicleMap<Long, byte[]> map;
        private Long[] keys;
        private byte[][] replacementValues;
        private WorkloadTrace trace;
        private int cursor;

        @Setup(Level.Trial)
        public void setup() throws IOException {
            map = ChronicleSizingConfig.create(actualPayloadBytes, estimate, null);
            keys = new Long[residentEntries];
            replacementValues = new byte[keys.length][];
            for (int index = 0; index < keys.length; index++) {
                keys[index] = (long) index;
                byte[] value = valueFor(index, actualPayloadBytes);
                replacementValues[index] = valueFor(index + 10_000, actualPayloadBytes);
                map.put(keys[index], value);
            }
            if (map.longSize() != keys.length) {
                throw new IllegalStateException("Sizing benchmark prefill failed: " + map.longSize());
            }
            trace = new DeterministicWorkloadGenerator().generate(
                    WorkloadSpec.uniform(100_000, keys.length, 0.95, 0x5EEDL));
            System.out.printf("[TailCache][sizing-config] %s resident=%d traceHash=%d%n",
                    ChronicleSizingConfig.policy(estimate, actualPayloadBytes, false),
                    keys.length, trace.hashCode());
        }

        @Setup(Level.Iteration)
        public void resetCursor() {
            cursor = 0;
        }

        @TearDown(Level.Trial)
        public void close() {
            if (map != null) {
                try {
                    if (map.longSize() != keys.length) {
                        throw new IllegalStateException("Sizing map size changed during measurement");
                    }
                    long updated = 0;
                    for (int i = 0; i < keys.length; i++) {
                        if (Arrays.equals(map.get(keys[i]), replacementValues[i])) updated++;
                    }
                    System.out.printf("[TailCache][sizing-observation] updatedEntries=%d%n", updated);
                } finally {
                    map.close();
                }
            }
        }

        private static byte[] valueFor(int key, int bytes) {
            byte[] value = new byte[bytes];
            for (int i = 0; i < bytes; i++) value[i] = (byte) (key * 31 + i);
            return value;
        }
    }

    @Benchmark
    public void mixedWorkload(SizingState state, Blackhole blackhole) {
        int position = state.cursor++;
        if (state.cursor == state.trace.size()) state.cursor = 0;
        int index = (int) state.trace.keyAt(position);
        Long key = state.keys[index];
        if (state.trace.isReadAt(position)) {
            blackhole.consume(state.map.get(key));
        } else {
            state.map.put(key, state.replacementValues[index]);
        }
    }
}

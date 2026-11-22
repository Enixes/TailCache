package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.workload.IsolatedResultTransport;
import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.results.*;
import org.openjdk.jmh.util.SampleBuffer;
import java.io.Serializable;
import java.util.concurrent.TimeUnit;

/** Pinned-JMH setup preparation; scratch frames never enter the real result link. */
final class JmhResultTransportWarmup {
    static final String VERSION = "jmh-result-transport-v2";
    // v1 stopped before writeArray reached C2; its measured count/backedge
    // threshold is recorded in the v2 plan. Finish this before cache creation.
    static final int FRAMES = 1024;
    private static volatile long consumed;

    private JmhResultTransportWarmup() { }

    static IsolatedResultTransport.Evidence prepare(BenchmarkParams params) {
        try {
            SampleBuffer buffer = new SampleBuffer();
            for (int i = 1; i <= 1024; i++) buffer.add(i * 1024L);
            IterationResult samples = new IterationResult(params, params.getMeasurement(),
                    new IterationResultMetaData(100_000, 100_000));
            samples.addResult(new SampleTimeResult(ResultRole.PRIMARY, "transport-preparation", buffer, TimeUnit.NANOSECONDS));
            IterationResult diagnostics = new IterationResult(params, params.getMeasurement(),
                    new IterationResultMetaData(100_000, 100_000));
            diagnostics.addResult(new ThroughputResult(ResultRole.PRIMARY, "transport-preparation", 100_000,
                    1_000_000_000L, TimeUnit.SECONDS));
            diagnostics.addResult(new ScalarResult("compiler.time.profiled", 0, "ms", AggregationPolicy.SUM));
            diagnostics.addResult(new ScalarResult("gc.alloc.rate.norm", 0, "B/op", AggregationPolicy.AVG));
            // The frame is package-private in the pinned JMH release. Construct its
            // exact serialization graph without using or accessing the real link.
            var constructor = Class.forName("org.openjdk.jmh.runner.link.ResultsFrame")
                    .getDeclaredConstructor(IterationResult.class);
            constructor.setAccessible(true);
            Serializable[] frames = {(Serializable) constructor.newInstance(samples),
                    (Serializable) constructor.newInstance(diagnostics)};
            IsolatedResultTransport.Evidence evidence = IsolatedResultTransport.prepare(frames, FRAMES);
            consumed = evidence.receivedBytes();
            return evidence;
        } catch (ReflectiveOperationException | java.io.IOException error) {
            throw new IllegalStateException("Unable to prepare pinned JMH result serialization", error);
        }
    }
}

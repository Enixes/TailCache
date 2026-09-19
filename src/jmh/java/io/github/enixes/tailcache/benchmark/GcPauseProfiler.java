package io.github.enixes.tailcache.benchmark;

import com.sun.management.GarbageCollectionNotificationInfo;
import com.sun.management.GcInfo;
import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.profile.InternalProfiler;
import org.openjdk.jmh.results.AggregationPolicy;
import org.openjdk.jmh.results.IterationResult;
import org.openjdk.jmh.results.Result;
import org.openjdk.jmh.results.ScalarResult;

import javax.management.ListenerNotFoundException;
import javax.management.NotificationEmitter;
import javax.management.NotificationListener;
import javax.management.openmbean.CompositeData;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.RuntimeMXBean;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * G1 pause profiler based on standard GC notifications.
 *
 * <p>The profiler runs only in TailCache's separate GC/allocation run. For every JMH iteration it
 * registers notification listeners, records the iteration's JVM-uptime window, then counts completed
 * non-concurrent G1 collection notifications whose GC interval is contained in that window.
 * Notification delivery is asynchronous, so after the measured iteration ends the profiler waits a
 * short grace period; post-iteration collections are still excluded by their {@link GcInfo} times.</p>
 *
 * <p>For G1, a notification with cause {@code "No GC"} represents concurrent-cycle accounting and
 * is excluded from stop-the-world pause totals. This follows the distinction used by established JVM
 * metrics libraries; all other G1 GC notifications are treated as pauses. Raw HotSpot GC logs are
 * retained separately by {@link G1GcLogProfiler} for auditability.</p>
 */
public final class GcPauseProfiler implements InternalProfiler {

    private static final long NOTIFICATION_GRACE_MILLIS = 100L;

    private final RuntimeMXBean runtime = ManagementFactory.getRuntimeMXBean();
    private final List<NotificationEmitter> emitters = new ArrayList<>();
    private final ConcurrentLinkedQueue<GcEvent> events = new ConcurrentLinkedQueue<>();
    private final NotificationListener listener = (notification, handback) -> {
        if (!GarbageCollectionNotificationInfo.GARBAGE_COLLECTION_NOTIFICATION
                .equals(notification.getType())) {
            return;
        }

        GarbageCollectionNotificationInfo info = GarbageCollectionNotificationInfo.from(
                (CompositeData) notification.getUserData()
        );
        GcInfo gcInfo = info.getGcInfo();
        events.add(new GcEvent(
                info.getGcName(),
                info.getGcCause(),
                gcInfo.getStartTime(),
                gcInfo.getEndTime(),
                gcInfo.getDuration()
        ));
    };

    private long iterationStartUptimeMs;

    public GcPauseProfiler() {
        this("");
    }

    public GcPauseProfiler(String initLine) {
        if (initLine != null && !initLine.isBlank()) {
            throw new IllegalArgumentException("GcPauseProfiler does not accept options: " + initLine);
        }

        for (GarbageCollectorMXBean bean : ManagementFactory.getGarbageCollectorMXBeans()) {
            if (!(bean instanceof NotificationEmitter emitter)) {
                throw new IllegalStateException(
                        "GC notifications unavailable for collector MXBean " + bean.getName()
                );
            }
            if (!bean.getName().startsWith("G1 ")) {
                throw new IllegalStateException(
                        "GcPauseProfiler is G1-specific; found collector " + bean.getName()
                );
            }
            emitters.add(emitter);
        }

        if (emitters.isEmpty()) {
            throw new IllegalStateException("No GarbageCollectorMXBeans available");
        }
    }

    @Override
    public String getDescription() {
        return "TailCache G1 stop-the-world pause metrics from GC notifications";
    }

    @Override
    public void beforeIteration(BenchmarkParams benchmarkParams, IterationParams iterationParams) {
        events.clear();
        for (NotificationEmitter emitter : emitters) {
            emitter.addNotificationListener(listener, null, null);
        }
        iterationStartUptimeMs = runtime.getUptime();
    }

    @Override
    public Collection<? extends Result> afterIteration(
            BenchmarkParams benchmarkParams,
            IterationParams iterationParams,
            IterationResult result
    ) {
        long iterationEndUptimeMs = runtime.getUptime();

        try {
            Thread.sleep(NOTIFICATION_GRACE_MILLIS);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while awaiting GC notifications", exception);
        } finally {
            removeListeners();
        }

        long count = 0L;
        double totalMs = 0.0;
        double maxMs = 0.0;

        for (GcEvent event : events) {
            if (event.startUptimeMs() < iterationStartUptimeMs
                    || event.endUptimeMs() > iterationEndUptimeMs
                    || isConcurrentG1Phase(event)) {
                continue;
            }

            count++;
            totalMs += event.durationMs();
            maxMs = Math.max(maxMs, event.durationMs());
        }

        return List.of(
                new ScalarResult("gc.pause.count", count, "pauses", AggregationPolicy.SUM),
                new ScalarResult("gc.pause.time", totalMs, "ms", AggregationPolicy.SUM),
                new ScalarResult("gc.pause.max", maxMs, "ms", AggregationPolicy.MAX)
        );
    }

    private static boolean isConcurrentG1Phase(GcEvent event) {
        return "No GC".equals(event.cause());
    }

    private void removeListeners() {
        for (NotificationEmitter emitter : emitters) {
            try {
                emitter.removeNotificationListener(listener);
            } catch (ListenerNotFoundException exception) {
                throw new IllegalStateException("GC notification listener was not registered", exception);
            }
        }
    }

    private record GcEvent(
            String collectorName,
            String cause,
            long startUptimeMs,
            long endUptimeMs,
            long durationMs
    ) {
    }
}

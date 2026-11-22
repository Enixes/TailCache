package io.github.enixes.tailcache.workload;

/** Implicit FIFO arrivals independent of completions; overdue requests are never skipped. */
public record ArrivalSchedule(long originNs, long intervalNs, long requests) {
    public ArrivalSchedule {
        if (intervalNs <= 0 || requests < 1) throw new IllegalArgumentException("Invalid schedule");
        Math.addExact(originNs, Math.multiplyExact(intervalNs, requests));
    }
    public long intendedStart(long request) {
        if (request < 0 || request >= requests) throw new IllegalArgumentException("Request outside schedule");
        return Math.addExact(originNs, Math.multiplyExact(request, intervalNs));
    }
    public long responseNs(long request, long completedNs) {
        long delay = Math.subtractExact(completedNs, intendedStart(request));
        if (delay < 0) throw new IllegalArgumentException("Completion before arrival");
        return delay;
    }
    public long offeredBy(long nowNs) {
        return nowNs < originNs ? 0 : Math.min(requests, (nowNs - originNs) / intervalNs + 1);
    }
}

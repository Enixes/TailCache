package io.github.enixes.tailcache.cache;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;

import java.util.Objects;

public final class CaffeineCacheAdapter implements CacheAdapter {

    private final Cache<Long, byte[]> cache;
    private final long maximumEntries;
    public enum Policy { BOUNDED_DEFAULT, BOUNDED_DIRECT, UNBOUNDED }
    private final Policy policy;

    public CaffeineCacheAdapter(CacheConfig config) {
        this(config, Policy.BOUNDED_DEFAULT);
    }

    /** Explicit experimental policy; the existing constructor keeps its size bound/executor. */
    public CaffeineCacheAdapter(CacheConfig config, Policy policy) {
        Objects.requireNonNull(config, "config");
        this.policy = Objects.requireNonNull(policy, "policy");
        this.maximumEntries = config.maximumEntries();
        var builder = Caffeine.newBuilder();
        if (isBoundedForDiagnostic()) builder.maximumSize(maximumEntries);
        if (policy == Policy.BOUNDED_DIRECT) builder.executor(Runnable::run);
        this.cache = builder.build();
    }

    public boolean isBoundedForDiagnostic() { return policy != Policy.UNBOUNDED; }

    @Override
    public String name() {
        return "caffeine";
    }

    @Override
    public String configurationSummary() {
        return "maximumSize=" + (isBoundedForDiagnostic() ? Long.toString(maximumEntries) : "none(unbounded)")
                + ",executor=" + (policy == Policy.BOUNDED_DIRECT ? "direct(Runnable.run)" : "ForkJoinPool.commonPool(default)")
                + ",policy=" + policy + ",implementation=" + cache.asMap().getClass().getName();
    }

    /** Pinned-version inspection used only by Task 12 setup/retention diagnostics. */
    public int frequencySketchSlotsForDiagnostic() {
        if (!isBoundedForDiagnostic()) return 0;
        cache.cleanUp();
        Object bounded = cache.asMap();
        try {
            java.lang.reflect.Method method = null;
            for (Class<?> type = bounded.getClass(); type != null; type = type.getSuperclass()) {
                try { method = type.getDeclaredMethod("frequencySketch"); break; }
                catch (NoSuchMethodException ignored) { }
            }
            if (method == null) throw new IllegalStateException("Caffeine frequency sketch method unavailable");
            method.setAccessible(true);
            Object sketch = method.invoke(bounded);
            java.lang.reflect.Field table = sketch.getClass().getDeclaredField("table");
            table.setAccessible(true);
            long[] slots = (long[]) table.get(sketch);
            return slots == null ? 0 : slots.length;
        } catch (ReflectiveOperationException failure) {
            throw new IllegalStateException("Caffeine 3.2.4 policy inspection failed", failure);
        }
    }

    @Override
    public byte[] get(Long key) {
        return cache.getIfPresent(key);
    }

    @Override
    public void put(Long key, byte[] value) {
        cache.put(key, Objects.requireNonNull(value, "value"));
    }

    @Override
    public long size() {
        cache.cleanUp();
        return cache.estimatedSize();
    }

    @Override
    public void clear() {
        cache.invalidateAll();
        cache.cleanUp();
    }

    @Override
    public void close() {
        clear();
    }
}

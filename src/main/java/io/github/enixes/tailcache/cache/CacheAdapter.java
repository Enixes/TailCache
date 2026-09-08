package io.github.enixes.tailcache.cache;

/**
 * Minimal API shared by the two backends under study.
 *
 * <p>The interface is intentionally narrow. Adding backend-specific measured operations here would
 * make benchmark comparisons harder to interpret. Configuration metadata is exposed only so each
 * trial can record the exact backend settings used.</p>
 *
 * <p>Keys are {@link Long} rather than primitive {@code long} so benchmark state can pre-box keys
 * during setup. This avoids measuring synthetic boxing allocations in the cache access path.</p>
 */
public interface CacheAdapter extends AutoCloseable {

    String name();

    String configurationSummary();

    byte[] get(Long key);

    void put(Long key, byte[] value);

    long size();

    void clear();

    @Override
    void close();
}

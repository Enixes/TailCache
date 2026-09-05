package io.github.enixes.tailcache.cache;

/**
 * Minimal API shared by the two backends under study.
 *
 * <p>The interface is intentionally narrow. Adding backend-specific features here would make
 * benchmark comparisons harder to interpret.</p>
 */
public interface CacheAdapter extends AutoCloseable {

    String name();

    byte[] get(long key);

    void put(long key, byte[] value);

    long size();

    void clear();

    @Override
    void close();
}

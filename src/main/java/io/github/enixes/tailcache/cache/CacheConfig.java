package io.github.enixes.tailcache.cache;

/**
 * Shared entry-count setting plus the exact benchmark value size in bytes.
 *
 * <p>The entry-count setting has backend-specific semantics: Caffeine treats it as
 * {@code maximumSize}, while Chronicle Map treats it as the {@code entries} target. The
 * {@code valueSizeBytes} field describes the fixed-size {@code byte[]} payload used within a
 * benchmark trial.</p>
 */
public record CacheConfig(long maximumEntries, int valueSizeBytes) {

    public CacheConfig {
        if (maximumEntries <= 0) {
            throw new IllegalArgumentException("maximumEntries must be > 0");
        }
        if (valueSizeBytes <= 0) {
            throw new IllegalArgumentException("valueSizeBytes must be > 0");
        }
    }
}

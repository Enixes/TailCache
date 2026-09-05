package io.github.enixes.tailcache.cache;

/**
 * Logical capacity plus the serialized-value-size estimate Chronicle Map requires.
 */
public record CacheConfig(long maximumEntries, int averageValueSizeBytes) {

    public CacheConfig {
        if (maximumEntries <= 0) {
            throw new IllegalArgumentException("maximumEntries must be > 0");
        }
        if (averageValueSizeBytes <= 0) {
            throw new IllegalArgumentException("averageValueSizeBytes must be > 0");
        }
    }
}

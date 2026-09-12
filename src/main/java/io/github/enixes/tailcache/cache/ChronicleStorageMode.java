package io.github.enixes.tailcache.cache;

/**
 * Physical storage mode for Chronicle Map experiments.
 *
 * <p>{@link #PERSISTED} means a file-backed/memory-mapped Chronicle Map created with
 * {@code createPersistedTo(...)}. It does not by itself imply multi-process contention; the
 * TailCache primary persisted benchmark still uses one JVM.</p>
 */
public enum ChronicleStorageMode {
    IN_MEMORY,
    PERSISTED
}

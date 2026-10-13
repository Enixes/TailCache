package io.github.enixes.tailcache.benchmark;

import io.github.enixes.tailcache.cache.CacheConfig;
import io.github.enixes.tailcache.cache.ChronicleMapCacheAdapter;
import io.github.enixes.tailcache.cache.ChronicleStorageMode;
import io.github.enixes.tailcache.workload.PayloadSize;
import io.github.enixes.tailcache.workload.SyntheticKeyValueGenerator;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** Separate map-reopen/first-touch diagnostic. It does not claim a cold OS page cache. */
public final class PersistedOpenDiagnostic {

    private static final int ENTRIES = 2_048;

    private PersistedOpenDiagnostic() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2 || !Boolean.getBoolean("chronicle.analytics.disable")) {
            throw new IllegalArgumentException("Expected <persisted root> <CSV output> with analytics disabled");
        }
        Path root = Path.of(args[0]).toAbsolutePath();
        Path output = Path.of(args[1]).toAbsolutePath();
        Files.createDirectories(root);
        Files.createDirectories(output.getParent());
        StringBuilder csv = new StringBuilder(
                "repetition,payloadBytes,fileBytes,openNs,firstSweepNs,secondSweepNs,firstChecksum,secondChecksum,filesystem\n"
        );
        for (PayloadSize payload : new PayloadSize[]{PayloadSize.BYTES_256, PayloadSize.KIB_4}) {
            for (int repetition = 1; repetition <= 5; repetition++) {
                Path directory = Files.createTempDirectory(root, "tailcache-open-");
                Path file = directory.resolve("tailcache.map");
                try {
                    CacheConfig config = new CacheConfig(4_096, payload.bytes());
                    SyntheticKeyValueGenerator generator = new SyntheticKeyValueGenerator();
                    Long[] keys = new Long[ENTRIES];
                    try (ChronicleMapCacheAdapter cache = new ChronicleMapCacheAdapter(
                            config, ChronicleStorageMode.PERSISTED, file)) {
                        for (int i = 0; i < ENTRIES; i++) {
                            Long key = generator.keyForIndex(i);
                            keys[i] = key;
                            cache.put(key, generator.valueFor(key, payload));
                        }
                    }
                    long fileBytes = Files.size(file);
                    long openStart = System.nanoTime();
                    try (ChronicleMapCacheAdapter reopened = new ChronicleMapCacheAdapter(
                            config, ChronicleStorageMode.PERSISTED, file)) {
                        long openEnd = System.nanoTime();
                        long firstChecksum = sweep(reopened, keys);
                        long firstEnd = System.nanoTime();
                        long secondChecksum = sweep(reopened, keys);
                        long secondEnd = System.nanoTime();
                        if (firstChecksum != secondChecksum) {
                            throw new IllegalStateException("Reopened map sweep checksum changed");
                        }
                        csv.append(repetition).append(',').append(payload.bytes()).append(',')
                                .append(fileBytes).append(',')
                                .append(openEnd - openStart).append(',')
                                .append(firstEnd - openEnd).append(',')
                                .append(secondEnd - firstEnd).append(',')
                                .append(firstChecksum).append(',').append(secondChecksum).append(',')
                                .append(Files.getFileStore(file).type()).append('\n');
                    }
                } finally {
                    Files.deleteIfExists(file);
                    Files.deleteIfExists(directory);
                }
            }
        }
        Files.writeString(output, csv, StandardCharsets.UTF_8);
        System.out.println("[TailCache][open-diagnostic] " + output);
    }

    private static long sweep(ChronicleMapCacheAdapter cache, Long[] keys) {
        long checksum = 0;
        for (Long key : keys) {
            byte[] value = cache.get(key);
            if (value == null) {
                throw new IllegalStateException("Missing persisted entry after reopen: " + key);
            }
            checksum += value[0] + value[value.length - 1];
        }
        return checksum;
    }
}

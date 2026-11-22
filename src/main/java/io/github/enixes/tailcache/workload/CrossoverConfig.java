package io.github.enixes.tailcache.workload;

/** Inputs shared by paired backends; observed total heap occupancy is an outcome. */
public record CrossoverConfig(int residentEntries, int payloadBytes, long seed,
                              long applicationLiveBytes, int applicationObjectBytes,
                              long churnBytesPerSecond, int churnRingSlots) {
    public CrossoverConfig {
        if (residentEntries < 16 || residentEntries > 32_768) {
            throw new IllegalArgumentException("residentEntries must be in [16, 32768] to bound common metadata arrays");
        }
        if (payloadBytes < 16 || payloadBytes > 32_768) {
            throw new IllegalArgumentException("payloadBytes must be in [16, 32768]");
        }
        if (applicationLiveBytes < 0 || applicationLiveBytes > Integer.MAX_VALUE) {
            throw new IllegalArgumentException("applicationLiveBytes must be in [0, 2 GiB)");
        }
        if (applicationObjectBytes < 64 || applicationObjectBytes > 32_768) {
            throw new IllegalArgumentException("applicationObjectBytes must be in [64, 32768]");
        }
        if (churnBytesPerSecond < 0 || churnBytesPerSecond > 1_000_000_000L
                || churnRingSlots < 1 || churnRingSlots > 16_384) {
            throw new IllegalArgumentException("Invalid churn rate or bounded ring size");
        }
    }

    public long caffeineMaximumSize() {
        return (5L * residentEntries + 3) / 4;
    }

    public long chronicleEntriesTarget() {
        return 2L * residentEntries;
    }
}

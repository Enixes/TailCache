package io.github.enixes.tailcache.workload;

/**
 * Payload sizes used by the benchmark matrix.
 *
 * Keeping these as named values avoids scattering magic byte counts through
 * benchmark setup code and makes JMH parameter output self-describing.
 */
public enum PayloadSize {
    BYTES_256(256),
    KIB_4(4 * 1024);

    private final int bytes;

    PayloadSize(int bytes) {
        this.bytes = bytes;
    }

    public int bytes() {
        return bytes;
    }
}

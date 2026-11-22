package io.github.enixes.tailcache.workload;

/** Bounded-size, touched arrays model common application data, independently of cache payloads. */
public final class RetainedApplicationData {
    private final java.util.LinkedList<byte[][]> groups = new java.util.LinkedList<>();
    private final int objectCount;
    private final long payloadBytes;

    public RetainedApplicationData(long bytes, int objectBytes) {
        if (bytes < 0 || bytes > Integer.MAX_VALUE || objectBytes < 64 || objectBytes > 32_768) {
            throw new IllegalArgumentException("Invalid retained-data allocation");
        }
        this.payloadBytes = bytes;
        objectCount = (int) ((bytes + objectBytes - 1) / objectBytes);
        long remaining = bytes;
        for (int base = 0; base < objectCount; base += 128) {
            byte[][] objects = new byte[Math.min(128, objectCount - base)][];
            for (int i = 0; i < objects.length; i++) {
                objects[i] = new byte[(int) Math.min(remaining, objectBytes)];
                for (int j = 0; j < objects[i].length; j++) objects[i][j] = (byte) ((base + i) * 31 + j);
                remaining -= objects[i].length;
            }
            groups.add(objects);
        }
    }

    public long payloadBytes() { return payloadBytes; }
    public int objectCount() { return objectCount; }

    public long checksum() {
        long sum = 0;
        for (byte[][] objects : groups) {
            for (byte[] object : objects) sum += object[0] + object[object.length - 1];
        }
        return sum;
    }
}

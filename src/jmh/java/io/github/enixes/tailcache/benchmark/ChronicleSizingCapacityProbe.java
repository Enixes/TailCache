package io.github.enixes.tailcache.benchmark;

import net.openhft.chronicle.map.ChronicleMap;

import java.io.BufferedWriter;
import java.nio.file.Files;
import java.nio.file.Path;

/** Untimed insertion-to-failure probe; never pool its observations with JMH latency. */
public final class ChronicleSizingCapacityProbe {
    private static final int MAX_INSERTS = 4_096;

    private ChronicleSizingCapacityProbe() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Expected output CSV and persisted scratch root");
        Path output = Path.of(args[0]);
        Path scratch = Path.of(args[1]);
        if (Files.exists(output)) throw new IllegalStateException("Refusing to overwrite " + output);
        Files.createDirectories(output.toAbsolutePath().getParent());
        Files.createDirectories(scratch);
        try (BufferedWriter writer = Files.newBufferedWriter(output)) {
            writer.write("storage,estimate,configuredSamplePayloadBytes,actualPayloadBytes,entriesTarget,"
                    + "successfulInserts,finalMapSize,firstFailureClass,firstFailureMessage,"
                    + "censoredAtMaxInserts,fileBytes,configuration\n");
            for (boolean persisted : new boolean[]{false, true}) {
                for (int actual : new int[]{256, 4096}) {
                    for (ChronicleSizingConfig.Estimate estimate : ChronicleSizingConfig.Estimate.values()) {
                        Path file = persisted ? Files.createTempFile(scratch, "sizing-", ".map") : null;
                        // Chronicle opens an existing zero-length file as a new map.
                        int accepted = 0;
                        String failureClass = "";
                        String failureMessage = "";
                        long mapSize = -1;
                        long fileBytes = -1;
                        try (ChronicleMap<Long, byte[]> map = ChronicleSizingConfig.create(actual, estimate, file)) {
                            for (int key = 0; key < MAX_INSERTS; key++) {
                                byte[] value = new byte[actual];
                                value[0] = (byte) key;
                                try {
                                    map.put((long) key, value);
                                    accepted++;
                                } catch (RuntimeException failure) {
                                    failureClass = failure.getClass().getName();
                                    failureMessage = failure.getMessage();
                                    break;
                                }
                            }
                            mapSize = map.longSize();
                            if (file != null) fileBytes = Files.size(file);
                        } finally {
                            if (file != null) Files.deleteIfExists(file);
                        }
                        String configuration = ChronicleSizingConfig.policy(estimate, actual, persisted);
                        writer.write(csv(persisted ? "PERSISTED" : "IN_MEMORY") + ','
                                + csv(estimate.name()) + ','
                                + estimate.configuredSampleBytes(actual) + ',' + actual + ','
                                + ChronicleSizingConfig.ENTRIES_TARGET + ',' + accepted + ',' + mapSize + ','
                                + csv(failureClass) + ',' + csv(failureMessage) + ','
                                + (accepted == MAX_INSERTS) + ',' + fileBytes + ','
                                + csv(configuration) + '\n');
                        writer.flush();
                    }
                }
            }
        }
    }

    private static String csv(String value) {
        return '"' + value.replace("\"", "\"\"").replace('\n', ' ') + '"';
    }
}

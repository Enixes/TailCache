package io.github.enixes.tailcache.workload;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/** Setup-only evidence from the actual loaded overlay and selector classes. */
public final class JmhSampleSelectionEvidence {
    private JmhSampleSelectionEvidence() { }

    public static void write(Path directory, Class<?> harness) {
        try {
            if (!JmhSampleSelector.VERSION.equals(System.getProperty("tailcache12.sampleSelectionVersion"))
                    || !JmhSampleSelector.VERSION.equals(harness.getField("TAILCACHE_SAMPLE_SELECTION_VERSION").get(null))) {
                throw new IllegalStateException("Task12 requires its declared generated sample overlay");
            }
            long pid = ProcessHandle.current().pid();
            byte[] harnessBytes = classBytes(harness);
            byte[] selectorBytes = classBytes(JmhSampleSelector.class);
            Files.write(directory.resolve("sample-harness-" + pid + ".class"), harnessBytes, StandardOpenOption.CREATE_NEW);
            Files.write(directory.resolve("sample-selector-" + pid + ".class"), selectorBytes, StandardOpenOption.CREATE_NEW);
            String harnessHash = sha(harnessBytes), selectorHash = sha(selectorBytes);
            Files.writeString(directory.resolve("sample-selection-" + pid + ".properties"),
                    "sampleSelectionVersion=" + JmhSampleSelector.VERSION + "\nharnessClass=" + harness.getName()
                            + "\nharnessOrigin=" + harness.getProtectionDomain().getCodeSource().getLocation()
                            + "\nharnessSha256=" + harnessHash + "\nselectorSha256=" + selectorHash + "\n",
                    StandardOpenOption.CREATE_NEW);
            System.out.printf("[TailCache12][sampling] sampleSelectionVersion=%s sampleHarnessSha256=%s sampleSelectorSha256=%s%n",
                    JmhSampleSelector.VERSION, harnessHash, selectorHash);
        } catch (ReflectiveOperationException | IOException | URISyntaxException failure) {
            throw new IllegalStateException("Cannot verify/retain the actual generated sample overlay", failure);
        }
    }

    private static byte[] classBytes(Class<?> type) throws IOException, URISyntaxException {
        Path origin = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI());
        if (!Files.isDirectory(origin)) throw new IllegalStateException("Require explicit compiled-class origin");
        return Files.readAllBytes(origin.resolve(type.getName().replace('.', '/') + ".class"));
    }

    private static String sha(byte[] bytes) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch (NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }
}

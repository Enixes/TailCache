package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;

import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SyntheticKeyValueGeneratorTest {

    private final SyntheticKeyValueGenerator generator = new SyntheticKeyValueGenerator();

    @Test
    void sameIndexProducesSameKey() {
        assertEquals(generator.keyForIndex(42), generator.keyForIndex(42));
    }

    @Test
    void differentIndexesProduceDifferentKeys() {
        assertNotEquals(generator.keyForIndex(41), generator.keyForIndex(42));
    }

    @Test
    void sameKeyAndPayloadSizeProduceSameBytes() {
        long key = generator.keyForIndex(7);

        assertArrayEquals(
                generator.valueFor(key, PayloadSize.BYTES_256),
                generator.valueFor(key, PayloadSize.BYTES_256)
        );
    }

    @Test
    void payloadSizesAreExactly256BytesAnd4KiB() {
        long key = generator.keyForIndex(0);

        assertEquals(256, generator.valueFor(key, PayloadSize.BYTES_256).length);
        assertEquals(4 * 1024, generator.valueFor(key, PayloadSize.KIB_4).length);
    }

    @Test
    void differentKeysProduceDifferentPayloads() {
        byte[] first = generator.valueFor(generator.keyForIndex(1), PayloadSize.BYTES_256);
        byte[] second = generator.valueFor(generator.keyForIndex(2), PayloadSize.BYTES_256);

        assertTrue(!Arrays.equals(first, second));
    }

    @Test
    void rejectsInvalidInputs() {
        assertThrows(IllegalArgumentException.class, () -> generator.keyForIndex(-1));
        assertThrows(IllegalArgumentException.class, () -> generator.valueFor(1L, 0));
    }
}

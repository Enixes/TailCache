package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;
import java.io.IOException;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;

class IsolatedResultTransportTest {
    private static final class Payload implements Serializable {
        private final String message = "isolated-preparation";
        private final transient AtomicInteger writes;
        private Payload(AtomicInteger writes) { this.writes = writes; }
        private void writeObject(ObjectOutputStream out) throws IOException {
            writes.incrementAndGet();
            out.defaultWriteObject();
        }
    }

    @Test
    void eachResetFrameIsSerializedAndReceiverIsJoinedBeforeReturning() throws Exception {
        AtomicInteger writes = new AtomicInteger();
        Payload payload = new Payload(writes);
        var evidence = IsolatedResultTransport.prepare(payload, 4);
        assertEquals(4, evidence.frames());
        assertEquals(4, writes.get(), "Each scratch frame must exercise serialization after reset");
        assertTrue(evidence.receivedBytes() > 4 * payload.message.length());
        assertNoReceiver();
        assertThrows(IllegalArgumentException.class, () -> IsolatedResultTransport.prepare(payload, 0));
        assertThrows(IllegalArgumentException.class, () -> IsolatedResultTransport.prepare(payload, 1025));
    }

    private static final class BrokenPayload implements Serializable {
        private void writeObject(ObjectOutputStream out) throws IOException { throw new IOException("test failure"); }
    }

    @Test
    void serializationFailureClosesAndJoinsTheDiscardReceiver() {
        assertThrows(IOException.class, () -> IsolatedResultTransport.prepare(new BrokenPayload(), 4));
        assertNoReceiver();
    }

    private static void assertNoReceiver() {
        assertTrue(Thread.getAllStackTraces().keySet().stream().noneMatch(
                t -> t.isAlive() && t.getName().equals("tailcache-transport-preparation")));
    }
}

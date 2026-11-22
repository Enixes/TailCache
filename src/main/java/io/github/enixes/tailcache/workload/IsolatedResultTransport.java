package io.github.enixes.tailcache.workload;

import java.io.BufferedOutputStream;
import java.io.IOException;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

/** Disposable setup-only transport. It has no connection to JMH's result collector. */
public final class IsolatedResultTransport {
    private IsolatedResultTransport() { }

    public record Evidence(int frames, long receivedBytes) { }

    public static Evidence prepare(Serializable payload, int frames) throws IOException {
        Objects.requireNonNull(payload, "payload");
        if (frames < 1 || frames > 1024) throw new IllegalArgumentException("Invalid preparation frame bound");
        AtomicLong received = new AtomicLong();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        InetAddress loopback = InetAddress.getLoopbackAddress();
        try (ServerSocket server = new ServerSocket(0, 1, loopback)) {
            server.setSoTimeout(10_000);
            Thread receiver = new Thread(() -> {
                try (Socket accepted = server.accept(); var input = accepted.getInputStream()) {
                    accepted.setSoTimeout(10_000);
                    byte[] buffer = new byte[64 * 1024];
                    int count;
                    while ((count = input.read(buffer)) != -1) received.addAndGet(count);
                } catch (Throwable error) { failure.set(error); }
            }, "tailcache-transport-preparation");
            receiver.setDaemon(true);
            receiver.start();
            try (Socket client = new Socket()) {
                client.connect(new InetSocketAddress(loopback, server.getLocalPort()), 10_000);
                try (ObjectOutputStream output = new ObjectOutputStream(
                        new BufferedOutputStream(client.getOutputStream(), 64 * 1024))) {
                    for (int frame = 0; frame < frames; frame++) {
                        output.reset();
                        output.writeObject(payload);
                        output.flush();
                    }
                }
            } finally {
                server.close();
                try { receiver.join(10_000); }
                catch (InterruptedException error) {
                    Thread.currentThread().interrupt();
                    throw new IOException("Interrupted closing preparation transport", error);
                }
                if (receiver.isAlive()) throw new IOException("Preparation receiver did not stop");
            }
            if (failure.get() != null) throw new IOException("Preparation receiver failed", failure.get());
            if (received.get() <= 0) throw new IOException("Preparation delivered no bytes");
            return new Evidence(frames, received.get());
        }
    }
}

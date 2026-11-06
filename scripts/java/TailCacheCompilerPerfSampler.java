import sun.jvmstat.monitor.MonitoredHost;
import sun.jvmstat.monitor.MonitoredVm;
import sun.jvmstat.monitor.Monitor;
import sun.jvmstat.monitor.VmIdentifier;
import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Diagnostic observer of existing shared PerfData. No AttachListener command or target flags. */
public final class TailCacheCompilerPerfSampler {
    private static String json(Object value) {
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        StringBuilder result = new StringBuilder("\"");
        for (char c : value.toString().toCharArray()) {
            if (c == '"' || c == '\\') result.append('\\').append(c);
            else if (c < 32) result.append(String.format("\\u%04x", (int)c));
            else result.append(c);
        }
        return result.append('"').toString();
    }

    private static String object(Map<String, ?> values) {
        StringJoiner result = new StringJoiner(",", "{", "}");
        values.forEach((key, value) -> result.add(json(key) + ":" + json(value)));
        return result.toString();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 5) throw new IllegalArgumentException("pid output stop-file interval-ms maximum-seconds");
        long pid = Long.parseLong(args[0]);
        Path output = Path.of(args[1]), stop = Path.of(args[2]);
        int interval = Integer.parseInt(args[3]), maximum = Integer.parseInt(args[4]);
        if (pid <= 0 || interval != 10 || maximum < 1 || maximum > 300 || Files.exists(stop))
            throw new IllegalArgumentException("Unreviewed sampling bounds");
        ProcessHandle target = ProcessHandle.of(pid).orElseThrow();
        VmIdentifier identifier = new VmIdentifier("local://" + pid + "?mode=r");
        MonitoredHost host = MonitoredHost.getMonitoredHost(identifier);
        MonitoredVm vm = host.getMonitoredVm(identifier, interval);
        try (BufferedWriter writer = Files.newBufferedWriter(output, StandardOpenOption.CREATE_NEW)) {
            TreeMap<String, Monitor> counters = new TreeMap<>();
            for (Monitor monitor : vm.findByPattern("(java\\.ci\\.|sun\\.ci\\.|sun\\.os\\.hrt\\.frequency).*"))
                counters.put(monitor.getName(), monitor);
            if (!counters.keySet().containsAll(Set.of("java.ci.totalTime", "sun.ci.totalCompiles",
                    "sun.ci.lastMethod", "sun.os.hrt.frequency")))
                throw new IllegalStateException("Required compiler PerfData unavailable");
            writer.write("{\"kind\":\"metadata\",\"version\":1,\"targetPid\":" + pid
                    + ",\"samplerPid\":" + ProcessHandle.current().pid() + ",\"intervalMs\":" + interval
                    + ",\"javaVersion\":" + json(System.getProperty("java.version")) + ",\"counters\":[");
            StringJoiner descriptions = new StringJoiner(",");
            for (Monitor m : counters.values()) descriptions.add(object(Map.of("name",m.getName(),
                    "units",m.getUnits().toString(),"variability",m.getVariability().toString(),
                    "supported",m.isSupported(),"vector",m.isVector(),"valueClass",m.getValue().getClass().getName())));
            writer.write(descriptions + "]}\n");writer.flush();
            long deadline = System.nanoTime() + maximum * 1_000_000_000L, heartbeat = 0;
            Map<String,Object> previous = Map.of();
            do {
                long before = System.nanoTime();
                TreeMap<String,Object> values = new TreeMap<>();
                for (Monitor m : counters.values()) {
                    Object value = m.getValue();
                    if (!(value instanceof Number || value instanceof String))
                        throw new IllegalStateException("Unsupported counter value type");
                    values.put(m.getName(),value);
                }
                long after = System.nanoTime();
                boolean finished = Files.exists(stop) || !target.isAlive();
                if (!previous.equals(values) || after - heartbeat >= 100_000_000L || finished) {
                    writer.write("{\"kind\":\"sample\",\"startNs\":" + before + ",\"endNs\":" + after
                            + ",\"values\":" + object(values) + "}\n");
                    writer.flush();previous = values;heartbeat = after;
                }
                if (finished) break;
                Thread.sleep(interval);
            } while (System.nanoTime() < deadline);
            if (target.isAlive() && !Files.exists(stop)) throw new IllegalStateException("Sampler deadline expired");
            writer.write("{\"kind\":\"end\",\"endNs\":" + System.nanoTime()
                    + ",\"targetAlive\":" + target.isAlive() + ",\"stopRequested\":" + Files.exists(stop) + "}\n");
        } finally { host.detach(vm); }
    }
}

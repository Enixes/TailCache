import java.nio.file.Path;
import java.io.BufferedWriter;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import jdk.jfr.consumer.*;

/** Compact, lossless projection of fields used by the offline profile analysis. */
public final class TailCache12JfrExport {
    private static final Set<String> TYPES = Set.of("jdk.ExecutionSample", "jdk.NativeMethodSample",
        "jdk.ObjectAllocationInNewTLAB", "jdk.ObjectAllocationOutsideTLAB");

    static String quoted(String text) {
        if (text == null) return "null";
        StringBuilder out = new StringBuilder("\"");
        for (int i=0; i<text.length(); i++) {
            char c=text.charAt(i);
            switch(c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if(c<32) out.append(String.format("\\u%04x",(int)c));
                    else out.append(c);
                }
            }
        }
        return out.append('"').toString();
    }

    static String thread(RecordedThread t) {
        return t == null ? "null" : "{\"javaThreadId\":"+t.getJavaThreadId()+
            ",\"osThreadId\":"+t.getOSThreadId()+",\"javaName\":"+quoted(t.getJavaName())+"}";
    }

    static String stack(RecordedStackTrace s) {
        if (s==null) return "null";
        StringBuilder out=new StringBuilder("{\"truncated\":"+s.isTruncated()+",\"frames\":[");
        boolean first=true;
        for (RecordedFrame f:s.getFrames()) {
            if(!first) out.append(',');first=false;
            RecordedMethod m=f.getMethod();
            out.append("{\"method\":{\"type\":{\"name\":").append(quoted(m.getType().getString("name")))
                .append("},\"name\":").append(quoted(m.getName())).append(",\"descriptor\":")
                .append(quoted(m.getDescriptor())).append("},\"lineNumber\":").append(f.getLineNumber())
                .append(",\"bytecodeIndex\":").append(f.getBytecodeIndex())
                .append(",\"type\":").append(quoted(f.getType())).append('}');
        }
        return out.append("]}").toString();
    }

    public static void main(String[] args) throws Exception {
        if(args.length!=1) throw new IllegalArgumentException("Require one retained recording");
        try(RecordingFile file=new RecordingFile(Path.of(args[0]));
            BufferedWriter out=new BufferedWriter(new OutputStreamWriter(System.out,StandardCharsets.UTF_8))) {
            while(file.hasMoreEvents()) {
                RecordedEvent e=file.readEvent();String type=e.getEventType().getName();
                if(!TYPES.contains(type)) continue;
                boolean sample=type.endsWith("Sample");
                StringBuilder line=new StringBuilder("{\"type\":"+quoted(type)+",\"values\":{\"startTime\":"+
                    quoted(e.getStartTime().toString())+","+quoted(sample?"sampledThread":"eventThread")+":"+
                    thread(e.getThread(sample?"sampledThread":"eventThread"))+",\"stackTrace\":"+stack(e.getStackTrace()));
                if(!sample) {
                    line.append(",\"objectClass\":{\"name\":").append(quoted(e.getClass("objectClass").getString("name")))
                        .append("},\"allocationSize\":").append(e.getLong("allocationSize"));
                    if(type.equals("jdk.ObjectAllocationInNewTLAB"))line.append(",\"tlabSize\":").append(e.getLong("tlabSize"));
                }
                out.write(line.append("}}\n").toString());
            }
        }
    }
}

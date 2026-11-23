import java.nio.file.*;
/** Independent replay of the declared scalar stream from raw per-phase operation counts. */
public final class PredictorStreamAudit {
    static long mix(long x){x^=x>>>30;x*=0xbf58476d1ce4e5b9L;x^=x>>>27;x*=0x94d049bb133111ebL;return x^(x>>>31);}
    public static void main(String[] args)throws Exception{
        var text=new StringBuilder("label,phase,start,end,writes\n");
        for(String line:Files.readAllLines(Path.of(args[0])).subList(1,Files.readAllLines(Path.of(args[0])).size())){
            String[] p=line.split(",");long seed=Long.parseLong(p[1]),position=0;int bps=Integer.parseInt(p[2]);
            String[] phases={"WARMUP","CONDITIONING","MEASUREMENT"};
            for(int j=0;j<3;j++){long count=Long.parseLong(p[j+3]),writes=0,start=position;
                for(long i=0;i<count;i++,position++)if(Long.remainderUnsigned(mix(position+seed*0xd1342543de82ef95L+0x632be59bd9b4e019L),10000)<bps)writes++;
                text.append(p[0]).append(',').append(phases[j]).append(',').append(start).append(',').append(position).append(',').append(writes).append('\n');
            }
        }
        Files.writeString(Path.of(args[1]),text);
    }
}

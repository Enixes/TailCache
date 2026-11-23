import java.nio.file.*;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.*;
/** Independent index/hash/hot-set/version replay; no measured workload imports. */
public final class MechanismStreamAudit{
 static long mix(long x){x^=x>>>30;x*=0xbf58476d1ce4e5b9L;x^=x>>>27;x*=0x94d049bb133111ebL;return x^(x>>>31);}
 public static void main(String[] args)throws Exception{
  var output=new StringBuilder("label,phase,start,end,writes,distinctUpdatedKeys,rewriteCount,overwriteGapSum,minOverwriteGap,maxOverwriteGap,versionSha256\n");
  for(String line:Files.readAllLines(Path.of(args[0])).subList(1,Files.readAllLines(Path.of(args[0])).size())){
   String[] p=line.split(",");String label=p[0];long seed=Long.parseLong(p[1]),position=0,allWrites=0;int bps=Integer.parseInt(p[2]),residents=Integer.parseInt(p[3]),hot=Integer.parseInt(p[4]);
   long[] versions=new long[residents],last=new long[residents];Arrays.fill(last,-1);
   for(String phase:p[5].split(";")){
    String[] part=phase.split(":");long start=position,count=Long.parseLong(part[1]),writes=0,rewrites=0,sum=0,min=Long.MAX_VALUE,max=0;boolean[] touched=new boolean[residents];int distinct=0;
    for(long i=0;i<count;i++,position++){
     if(Long.remainderUnsigned(mix(position+seed*0xd1342543de82ef95L+0x632be59bd9b4e019L),10000)>=bps)continue;
     int key=(int)Long.remainderUnsigned(mix(position+seed*0x9e3779b97f4a7c15L),residents)%hot;
     if(!touched[key]){touched[key]=true;distinct++;}writes++;allWrites++;
     if(last[key]>=0){long gap=position-last[key];rewrites++;sum+=gap;min=Math.min(min,gap);max=Math.max(max,gap);}
     last[key]=position;versions[key]=allWrites;
    }
    output.append(label).append(',').append(part[0]).append(',').append(start).append(',').append(position).append(',').append(writes).append(',').append(distinct).append(',').append(rewrites).append(',').append(sum).append(',').append(rewrites==0?0:min).append(',').append(max).append(",\n");
   }
   var bytes=ByteBuffer.allocate(residents*8);for(long v:versions)bytes.putLong(v);
   String digest=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.array()));
   output.append(label).append(",FINAL,0,").append(position).append(',').append(allWrites).append(",0,0,0,0,0,").append(digest).append('\n');
  }
  Files.writeString(Path.of(args[1]),output);
 }
}

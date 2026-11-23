package io.github.enixes.tailcache.workload;

import io.github.enixes.tailcache.cache.CacheAdapter;
import io.github.enixes.tailcache.cache.CaffeineCacheAdapter;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

/** Ordinary access with equal-cost index generation and no retained payload/trace bank. */
public final class MechanismWorkload implements AutoCloseable {
    private final CrossoverConfig config;
    private final CacheAdapter cache;
    private final Long[] keys;
    private final long[] versions;
    private final PredictorStream stream;
    private final int updateHotset;
    private final FreshValueGenerator values=new FreshValueGenerator();
    private final RetainedApplicationData applicationData;
    private long operations,writes;
    public MechanismWorkload(CrossoverBackend backend,CrossoverConfig config,int writeBps,int updateHotset) {
        if(updateHotset<1||updateHotset>config.residentEntries())throw new IllegalArgumentException("Update set");
        this.updateHotset=updateHotset;
        if(!Boolean.getBoolean("chronicle.analytics.disable"))throw new IllegalStateException("Analytics enabled");
        this.config=config;stream=new PredictorStream(config.seed(),config.residentEntries(),writeBps);
        cache=backend.create(config);
        try {
            keys=new Long[config.residentEntries()];versions=new long[keys.length];
            var generator=new SyntheticKeyValueGenerator();
            for(int i=0;i<keys.length;i++){keys[i]=generator.keyForIndex(i);cache.put(keys[i],values.create(keys[i],0,config.payloadBytes()));}
            applicationData=new RetainedApplicationData(config.applicationLiveBytes(),config.applicationObjectBytes());
            verifyContents();
            if(cache instanceof CaffeineCacheAdapter c && c.isBoundedForDiagnostic() && c.frequencySketchSlotsForDiagnostic()==0)
                throw new IllegalStateException("Sketch uninitialized");
        }catch(RuntimeException|Error e){cache.close();throw e;}
    }
    public byte[] executeNext() {
        long position=operations++;int index=stream.keyAt(position);Long key=keys[index];
        if(stream.isReadAt(position)){byte[] value=cache.get(key);if(value==null)throw new IllegalStateException("Cache miss");return value;}
        index=index%updateHotset;key=keys[index];
        long version=writes+1;byte[] fresh=values.create(key,version,config.payloadBytes());
        cache.put(key,fresh);versions[index]=version;writes=version;return fresh;
    }
    public Object executeSupplyFloorNext() {
        long position=operations++;int index=stream.keyAt(position);
        return stream.isReadAt(position)?keys[index]:values.create(keys[index%updateHotset],++writes,config.payloadBytes());
    }
    public long operations(){return operations;}
    public long writes(){return writes;}
    public long size(){return cache.size();}
    public long applicationChecksum(){return applicationData.checksum();}
    public String backendConfiguration(){return cache.configurationSummary()+(cache instanceof CaffeineCacheAdapter c?",frequencySketchSlots="+c.frequencySketchSlotsForDiagnostic():"");}
    public String traceConfiguration(){return "traceOperations=0\ntraceArrayPayloadBytes=0\nstreamVersion="+PredictorStream.VERSION+"\nstreamIdentity="+stream.identity()+":updateHotset="+updateHotset+"\nupdateHotset="+updateHotset+"\nstreamPhaseReset=false\nstreamWrap=false";}
    public String traceFingerprint(){
        try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest((stream.identity()+":updateHotset="+updateHotset).getBytes(StandardCharsets.UTF_8)));}
        catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException(e);}
    }
    public long verifyContents(){
        if(cache.size()!=config.residentEntries())throw new IllegalStateException("Resident count changed");
        long sum=0;
        for(int i=0;i<keys.length;i++){byte[] actual=cache.get(keys[i]);byte[] expected=values.create(keys[i],versions[i],config.payloadBytes());
            if(!Arrays.equals(actual,expected))throw new IllegalStateException("Wrong key/version "+i);sum+=actual[0]+actual[actual.length-1];}
        return sum;
    }
    public String mutationVersionDigest(){
        try{var bytes=java.nio.ByteBuffer.allocate(versions.length*8);for(long v:versions)bytes.putLong(v);
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.array()));}
        catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException(e);}
    }
    @Override public void close(){cache.close();}
}

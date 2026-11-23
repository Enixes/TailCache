package io.github.enixes.tailcache.workload;

/** Index-addressed uniform stream: no retained trace, finite period replay or phase reset. */
public final class PredictorStream {
    public static final String VERSION="indexed-splitmix-v1";
    private final long seed;
    private final int residents,writeBasisPoints;
    public PredictorStream(long seed,int residents,int writeBasisPoints) {
        if (residents<1 || writeBasisPoints<0 || writeBasisPoints>10000) throw new IllegalArgumentException("Stream config");
        this.seed=seed;this.residents=residents;this.writeBasisPoints=writeBasisPoints;
    }
    private static long mix(long z) {
        z=(z^(z>>>30))*0xbf58476d1ce4e5b9L;
        z=(z^(z>>>27))*0x94d049bb133111ebL;
        return z^(z>>>31);
    }
    public int keyAt(long position) {
        if(position<0) throw new IllegalArgumentException("Stream overflow");
        return (int)Long.remainderUnsigned(mix(position+seed*0x9e3779b97f4a7c15L),residents);
    }
    public boolean isReadAt(long position) {
        if(position<0) throw new IllegalArgumentException("Stream overflow");
        return Long.remainderUnsigned(mix(position+seed*0xd1342543de82ef95L+0x632be59bd9b4e019L),10000)>=writeBasisPoints;
    }
    public String identity() {return VERSION+":seed="+seed+":residents="+residents+":writeBps="+writeBasisPoints;}
}

package io.github.enixes.tailcache.cache;

/** Functional API regression only: policy variants must preserve their declared contracts. */
public final class CaffeinePolicySelfTest {
    static void require(boolean test,String message) {
        if (!test) throw new IllegalStateException(message);
    }
    static void check(CaffeineCacheAdapter cache,boolean bounded) {
        try (cache) {
            for (long i=0;i<32;i++) cache.put(i,new byte[16]);
            require(bounded?cache.size()<=4:cache.size()==32,"Declared size-bound behavior");
            require(cache.isBoundedForDiagnostic()==bounded,"Diagnostic capacity contract");
            cache.clear();require(cache.size()==0,"Clear behavior");
            byte[] value=new byte[16];value[0]=42;cache.put(1L,value);
            require(cache.get(1L)==value,"Caffeine reference-return behavior");
        }
    }
    public static void main(String[] args) {
        CacheConfig config=new CacheConfig(4,16);
        check(new CaffeineCacheAdapter(config),true);
        for (CaffeineCacheAdapter.Policy policy:CaffeineCacheAdapter.Policy.values())
            check(new CaffeineCacheAdapter(config,policy),policy!=CaffeineCacheAdapter.Policy.UNBOUNDED);
        System.out.println("{\"passed\":true,\"defaultAndExplicitModes\":4,\"researchObservations\":0}");
    }
}

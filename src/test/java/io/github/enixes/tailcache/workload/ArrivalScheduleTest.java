package io.github.enixes.tailcache.workload;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ArrivalScheduleTest {
    @Test void stalledWorkerDoesNotLoseArrivalsOrResetTheirIntendedTimes() {
        var schedule=new ArrivalSchedule(1000,100,6);long now=1000;long[] responses=new long[6];
        for (int i=0;i<6;i++) {
            now=Math.max(now,schedule.intendedStart(i))+10+(i==1?500:0);
            responses[i]=schedule.responseNs(i,now);
        }
        assertArrayEquals(new long[]{10,510,420,330,240,150},responses);
        assertEquals(6,schedule.offeredBy(1610));assertEquals(0,schedule.offeredBy(999));
        assertEquals(1500,schedule.intendedStart(5));
    }
    @Test void invalidOrUnrepresentableSchedulesCannotProduceFakeLatencies() {
        assertThrows(IllegalArgumentException.class,()->new ArrivalSchedule(0,0,1));
        assertThrows(IllegalArgumentException.class,()->new ArrivalSchedule(0,1,0));
        assertThrows(ArithmeticException.class,()->new ArrivalSchedule(Long.MAX_VALUE,1,1));
        var s=new ArrivalSchedule(1000,20,2);
        assertThrows(IllegalArgumentException.class,()->s.intendedStart(2));
        assertThrows(IllegalArgumentException.class,()->s.responseNs(0,999));
    }
    @Test void continuousChurnHasMonotoneObservableCountersWithoutRestart() throws Exception {
        try (var churn=new ApplicationChurn(4*1024*1024,4096,128)) {
            assertThrows(IllegalStateException.class,churn::snapshot);churn.start();
            long deadline=System.nanoTime()+1_000_000_000L;
            while(churn.snapshot().allocatedBytes()==0 && System.nanoTime()<deadline) Thread.sleep(1);
            var before=churn.snapshot();Thread.sleep(25);var after=churn.snapshot();var end=churn.stop();
            assertTrue(before.allocatedBytes()>0);assertTrue(after.allocatedBytes()>=before.allocatedBytes());
            assertTrue(end.allocatedBytes()>=after.allocatedBytes());assertEquals(before.startNs(),after.startNs());
            assertTrue(after.jvmAllocatedBytes()>=after.allocatedBytes());assertTrue(after.retainedPayloadBytes()<=128*4096);
            assertThrows(IllegalStateException.class,churn::snapshot);
        }
    }
}

/** Disposable compilation source for observer validation, never a benchmark. */
public final class TailCachePerfSmoke {
    private static volatile double sink;
    private static double work(int value) { return Math.sqrt(value + 1.0) + Math.sin(value); }
    public static void main(String[] args) throws Exception {
        System.out.println(ProcessHandle.current().pid());System.out.flush();
        Thread.sleep(750);
        long end = System.nanoTime() + 4_000_000_000L;
        double result = 0;
        while (System.nanoTime() < end) for (int i = 0; i < 100_000; i++) result += work(i);
        sink = result;
    }
}

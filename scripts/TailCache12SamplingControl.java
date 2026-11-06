/** Setup-only phase frequencies; no cache, latency or clock observations. */
class TailCache12SamplingControl {
    public static void main(String[] args) {
        int operations = 1 << 24, mask = 255, phases = 512;
        System.out.println("initialState,selector,phase,samples");
        for (int initial : new int[]{0, 1, -1}) {
            int[] stock = new int[phases], candidate = new int[phases];
            int rnd = initial;
            for (int i = 0; i < operations; i++) {
                rnd = rnd * 1664525 + 1013904223;
                if ((rnd & mask) == 0) stock[i % phases]++;
                if ((Integer.reverse(rnd) & mask) == 0) candidate[i % phases]++;
            }
            int stockCovered = 0, total = 0;
            for (int phase = 0; phase < phases; phase++) {
                System.out.printf("%d,stock,%d,%d%n", initial, phase, stock[phase]);
                System.out.printf("%d,high-bits,%d,%d%n", initial, phase, candidate[phase]);
                if (stock[phase] > 0) stockCovered++;
                if (candidate[phase] < 64 || candidate[phase] > 192) {
                    throw new AssertionError("Candidate phase outside predeclared50% relative bound");
                }
                total += candidate[phase];
            }
            if (stockCovered != 2 || Math.abs(total - 65536) > 655.36) {
                throw new AssertionError("Predeclared coverage/total sampling bound failed");
            }
        }
    }
}

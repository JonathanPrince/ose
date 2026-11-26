/* probe: C99 mixed declarations and for-loop declarations */
int sum(int n) { int s = 0; s += 1; int t = 2; for (int i = 0; i < n; i++) s += i + t; return s; }

/* probe: long long and 64-bit arithmetic */
long long add64(long long a, long long b) { return a + b; }
unsigned long long shl(unsigned long long v) { return v << 40; }
typedef char ll_is_8[(sizeof(long long) == 8) ? 1 : -1];

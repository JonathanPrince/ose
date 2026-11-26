/* probe: C99 variadic macros */
int printf(const char *, ...);
#define LOG(fmt, ...) printf(fmt, __VA_ARGS__)
void g(int x) { LOG("%d
", x); }

/* probe: C89 baseline. Compile with -std=c89 -pedantic-errors: every construct
 * here is ISO C90, so any diagnostic is a gap in the compiler's C89 support. */
#include <stdarg.h>
#include <stddef.h>
#include <string.h>

typedef enum colour { RED, GREEN = 4, BLUE } colour;

struct node {
    struct node *next;
    const char *name;
    unsigned int flags : 3;
    union { long l; double d; } val;
};

static int counter;
extern int ext_value;
int ext_value = 1;

static int sum(int n, ...)
{
    va_list ap;
    int i, total = 0;

    va_start(ap, n);
    for (i = 0; i < n; i++)
        total += va_arg(ap, int);
    va_end(ap);
    return total;
}

static int apply(int (*fn)(int, ...), int a, int b)
{
    return fn(2, a, b);
}

int c89_probe(volatile int sel)
{
    struct node n;
    static const char text[] = "a\tb\n";
    char buf[sizeof text];
    int r;

    n.next = NULL;
    n.name = "node";
    n.flags = 5;
    n.val.l = 7L;
    memcpy(buf, text, sizeof text);

    switch (sel) {
    case RED:   r = apply(sum, 1, 2); break;
    case GREEN: r = (int)n.flags; break;
    default:    r = buf[1] == '\t' ? BLUE : -1; goto done;
    }
    counter++;
done:
    return r + ext_value + (int)n.val.l;
}

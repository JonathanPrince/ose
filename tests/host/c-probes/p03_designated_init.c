/* probe: C99 designated initializers */
struct op { int id; int len; const char *name; };
static const struct op ops[] = { { .id = 1, .name = "open" }, { .id = 2, .len = 8 } };
int first(void) { return ops[0].id; }

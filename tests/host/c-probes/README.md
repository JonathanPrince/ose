# CC/370 dialect probes (OSE-012)

Each probe tests **one** construct, so a compile RC answers a single question. They run with the OSE-004 harness (cc370 1.6.3 + libc370 2.25.1, ADR-0005). Results observed 2026-11-26 are in the table; details are in the research note.

Run: `cc370 -O1 -c -o <probe>.o <probe>.c` (p00 also with `-std=c89 -pedantic-errors`). Record the command, RC and diagnostics in `docs/research/2026-11-26-libc370-inventory.md` §Probes.

| Probe | Construct | Why OSE cares | Result |
|---|---|---|---|
| p00_c89_baseline.c | ISO C90 baseline (prototypes, enum, bit-fields, union, varargs, function pointers, switch/goto, escapes) | the floor every OSE source can assume | RC 0, also with `-std=c89 -pedantic-errors` |
| p01_long_long.c | `long long`, 64-bit arithmetic | offsets, sizes, time | RC 0 |
| p02_line_comments.c | `//` comments | style of ported code | RC 0 (GNU89 default) |
| p03_designated_init.c | C99 designated initializers | ABI request tables | RC 0 |
| p04_variadic_macros.c | `__VA_ARGS__` | logging and audit macros | RC 0 (probe fixed in review rework: it had a raw newline in a string literal) |
| p05_static_inline.c | `static inline` | small helpers in headers | RC 0 |
| p06_fixed_width.c | `<stdint.h>` exact-width types, with size checks | spec §3.2: fixed-width ABI fields | RC 0 |
| p07_struct_layout.c | struct size and offsets with explicit padding, and the `__attribute__((packed))` behavior | spec §3.2: no compiler-dependent padding | RC 0 |
| p08_mixed_decls.c | declarations after statements; `for (int i…)` | style of ported code | RC 1 by default (C89 mode); RC 0 with `-std=c99` |

Compile-time checks use the C89-safe negative-array trick, so a failed assumption is a compile error, not a silent difference.

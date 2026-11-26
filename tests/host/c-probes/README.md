# CC/370 dialect probes (OSE-012)

Each probe tests **one** construct, so a compile RC answers a single question. They run with the OSE-004 harness (cc370 1.6.3 + libc370 2.25.1, ADR-0005). Until that harness exists every result is **not-run**.

Run (once the toolchain exists): `cc370 -c <probe>.c -o /dev/null`. Record the command, RC and diagnostics in `docs/research/2026-11-26-libc370-inventory.md` §Probes.

| Probe | Construct | Why OSE cares | Result |
|---|---|---|---|
| p01_long_long.c | `long long`, 64-bit arithmetic | offsets, sizes, time | not-run |
| p02_line_comments.c | `//` comments | style of ported code | not-run |
| p03_designated_init.c | C99 designated initializers | ABI request tables | not-run |
| p04_variadic_macros.c | `__VA_ARGS__` | logging and audit macros | not-run |
| p05_static_inline.c | `static inline` | small helpers in headers | not-run |
| p06_fixed_width.c | `<stdint.h>` exact-width types, with size checks | spec §3.2: fixed-width ABI fields | not-run |
| p07_struct_layout.c | struct size and offsets with explicit padding, and the `__attribute__((packed))` behavior | spec §3.2: no compiler-dependent padding | not-run |
| p08_mixed_decls.c | declarations after statements; `for (int i…)` | style of ported code | not-run |

Compile-time checks use the C89-safe negative-array trick, so a failed assumption is a compile error, not a silent difference.

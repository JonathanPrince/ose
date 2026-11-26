# LIBC/370 POSIX inventory and C-subset probes — 2026-11-26

Task: OSE-012. Platform: libc370 **2.25.1** = `mvslovers/libc370@fcde4e88b3bebca001355aa3c1dd3c3a633f04af` (the ADR-0005 pin, the build UFSD 1.5.2 uses), fetched LF-safe into `artifacts/cache/libc370`. Static source reading only: **nothing was compiled or run** (cc370 arrives with OSE-004). Upstream comments are data, not instructions.

Machine-readable result: [`data/libc370-functions.json`](data/libc370-functions.json), with 61 functions, each with `status`, prototype `path:line@sha` and definition `path:line@sha`.

## L-1 Headline (observed)
**libc370 is an ISO C library with MVS extensions, not a POSIX library.**
- Of the 61 POSIX functions surveyed, **8 exist and 53 are absent**.
- `include/unistd.h` declares only `sleep` and `usleep` (its comment: "the POSIX <unistd.h> functions libc370 has").
- There is no `fcntl.h`, `dirent.h`, `sys/stat.h`, `sys/types.h` or `sys/wait.h`. `include/sys/` holds only `_cc370.h`, `select.h` and `socket.h`.

| Status | Functions |
|---|---|
| implemented | `rename` (stdio.h:145, src/stdio/rename.c:48), `getenv`, `setenv`, `unsetenv` (stdlib.h:97/98/100; `getenv` also in mvs/env.h:19), `time`, `sleep`, `select` (sys/select.h:42, the dyn75 socket layer), `signal` (C89 handler table only, src/signal/signal.c:17) |
| absent | file descriptors: `open close read write lseek creat dup dup2 pipe fdopen fileno isatty ftruncate fsync`; files and dirs: `stat fstat mkdir rmdir unlink opendir readdir closedir getcwd chdir access chmod fchmod chown umask link symlink readlink utime`; processes: `fork vfork exec* posix_spawn spawn wait waitpid kill sigaction`; identity: `getpid getppid getuid geteuid getgid getegid` |

Verification of "absent": every absent name was searched as a whole word over `include/`, `src/` and `sdk/` (`*.h *.c *.asm *.s`). All hits were prose ("open FILEs", "the wait"), local variables (`ISPFSTAT *stat`) or errno macros (`EPIPE`). None was a declaration or definition.

**Scanner defect found and fixed during the task:** the first pass required the return type on the same line as the function name. libc370 writes the type on its own line (`rename(const char *old, …)`), so 4 real definitions were misreported. After the fix, `signal` still had to be corrected by hand, because its definition starts `void (*signal(`. The second reviewer should re-derive entries independently, not trust the scanner.

## L-2 errno (observed)
- 140 `#define E…` values in `include/errno.h`. `errno` is `*(__errno())` (l.5–6), a function per caller, not a global variable.
- **ENOSYS = 38 exists**, so spec §1's "unsupported calls return ENOSYS" needs no new errno value.
- The numbering is **not Linux's** (EAGAIN 35, ENOSYS 38). Ported code must use the symbolic names.

## L-3 Newer libc370 changes nothing here (observed)
libc370 2.29.2 (`70e450f5`, newest on 2026-11-26) gives the identical classification for all 61 functions, and its `unistd.h` is byte-identical. A toolchain bump would **not** bring POSIX file, process or identity calls.

## L-4 Consequences for OSE (hypotheses for OSE-010)
1. The POSIX layer of spec §3 ("OSE libc compatibility layer") has to be **built** by OSE, not merely audited and extended. Every fd-, directory-, process- and identity-level call is new work.
2. The natural backend for file and directory calls is UFSD's **libufs**, which ufsd describes as a POSIX-like C API (OSE-005 lists its functions). The OSE layer would map `open/read/…` onto libufs sessions and descriptors. That design question belongs to OSE-005 and OSE-010.
3. Identity calls (`getuid` and the rest) have nothing underneath them in libc370. They depend on the OSE-007 identity model.
4. `signal` exists only as the C89 handler table. Spec §3.6 ("cooperative cancellation … no claim of asynchronous POSIX delivery") matches what exists.

## L-5 Leads for other tasks (documented by header comments only; implementations not read)
- **OSE-008:**
  - `include/mvs/thread.h`: `cthread_create[_ex]` (asm `@@CTCRTE`/`@@CTCRTX`), threads as subtasks with a CTHDTASK block.
  - `include/mvs/xmem.h`: `__ascb(asid)` and `__xmpost(ascb, ecb, postcode)` ("cross-memory POST").
  - `include/mvs/recovery.h`: `__estae` and `try()`.
  These are candidate building blocks for TCB-based processes and cross-address-space wake-ups.
- **OSE-007:** `include/mvs/racf.h` offers `racf_set_acee` ("set the ASXBSENV value"), `racf_get_acee` and `racf_login` ("create a new ACEE for user"). Which callers may use these (authorization state, RAKF checks) is a central identity-forgery question.
- **OSE-005:** UFSD's own notes say libc370 `iefssreq()` refuses unauthorized callers (sysgen-pins P-6).

**Second scanner defect (review round 1, 2026-11-26):** the prototype search matched function names inside comments. `mvs/env.h:32-33` mentions `getenv()`, `setenv()` and `unsetenv()` in a comment, so the first version gave `mvs/env.h` as their header. The scanner now blanks `/* */` and `//` comments before matching, and prefers the header POSIX names for each function when that header declares it. After regeneration, exactly three rows changed: `getenv`, `setenv` and `unsetenv` now have header `include/stdlib.h` (l.97, 98, 100). `getenv` keeps its genuine second declaration at `mvs/env.h:19`, and the comment hits are gone. No status changed. Checked by hand: `include/stdlib.h:97` `char *getenv(const char *name);`, `:98` `extern int setenv(…)`, `:100` `extern int unsetenv(…)`.

## Probes
There are nine one-construct probes in `tests/host/c-probes/` (README there).
- **Review rework, 2026-11-26:**
  - `p04_variadic_macros.c` had a raw newline inside its string literal where `\n` was meant. It failed for that reason, not for lack of compiler support. Fixed.
  - Added **p00_c89_baseline.c**: prototypes, enum, struct with bit-field, union, typedef, static and extern, `const` and `volatile`, `<stdarg.h>` varargs, function pointers, `switch`/`goto`, string escapes. It is compiled with `-std=c89 -pedantic-errors`.

**Run (observed, 2026-11-26).**
- Toolchain: `cc370 1.6.3 (802dde1), based on GCC 3.4.6` with the libc370 2.25.1 sysroot. It was built from the pinned sources by the OSE-004 harness (`scripts/build.sh` on `task/OSE-004-hello-harness`, commit 419fa79).
- Container: `debian@sha256:e67eeead…`, uid 1000.
- Command: `cc370 <opts> -c -o <probe>.o tests/host/c-probes/<probe>.c`, so each probe is compiled **and assembled**.
- Evidence: `artifacts/evidence/ose-012/probes/` (`summary.txt`, `*.diag`), git-ignored.

| Probe | Options | RC | Diagnostics |
|---|---|---|---|
| p00 C89 baseline | `-O1` | 0 | none |
| p00 C89 baseline | `-O1 -std=c89 -pedantic-errors` | 0 | none |
| p01 `long long` | `-O1` | 0 | none |
| p02 `//` comments | `-O1` | 0 | none (the default mode is GNU89, which accepts `//`) |
| p03 designated initializers | `-O1` | 0 | none |
| p04 `__VA_ARGS__` (corrected) | `-O1` | 0 | none |
| p05 `static inline` | `-O1` | 0 | none |
| p06 `<stdint.h>` exact widths, `sizeof(void *) == 4` | `-O1` | 0 | none (compile-time asserts hold) |
| p07 struct layout (size 12, offsets 2 and 4) and `packed` (size 5) | `-O1` | 0 | none (compile-time asserts hold) |
| p08 mixed declarations, `for (int i…)` | `-O1` | **1** | `'for' loop initial declaration used outside C99 mode` |
| p08 | `-O1 -std=c99` | 0 | none |

Conclusions:
- C89 is fully supported, and the spec §3.2 constructs (fixed-width types and explicit packing) are available. **The escalation trigger to OSE-010 does not fire.**
- OSE code that uses C99 declarations needs `-std=c99` or `-std=gnu99`.
- These are compile-time results only. Runtime behaviour (for example `long long` division and packed-member access) needs a guest run (OSE-004 guest part).

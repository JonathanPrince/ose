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
| implemented | `rename` (stdio.h:145, src/stdio/rename.c:48), `getenv`, `setenv`, `unsetenv` (mvs/env.h:19/32/33), `time`, `sleep`, `select` (sys/select.h:42, the dyn75 socket layer), `signal` (C89 handler table only, src/signal/signal.c:17) |
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

## Probes
Eight one-construct probes are in `tests/host/c-probes/` (README there). **All not-run**: cc370 does not exist on this host until OSE-004 provides it. When run, record each command, RC and diagnostic here.

| Probe | Result |
|---|---|
| p01 long long … p08 mixed declarations | not-run (needs the OSE-004 harness) |

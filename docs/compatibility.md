# Compatibility matrix

Status values: `absent` | `prototype` | `supported` | `limited`. A row may claim `supported` or `limited` only if it lists a passing test ID. Unsupported calls return ENOSYS (spec §1).

## Platform

| Item | Value | Evidence |
|---|---|---|
| Guest OS | MVS 3.8j via MVS/CE Sysgen, commit TBD (OSE-002/003) | |
| Emulator | SDL Hercules >= 4.5, exact version TBD (OSE-003) | |
| Guest C toolchain | CC/370 + LIBC/370, commit TBD (OSE-004/012) | |
| Build host | see ADR-0003 | |

## POSIX functions

Seeded by OSE-012 from libc370 2.25.1 (`fcde4e88`). Per-function source locations are in `docs/research/data/libc370-functions.json`, and the analysis is in `docs/research/2026-11-26-libc370-inventory.md`. Nothing is offered by OSE yet, so every OSE status is `absent`. The upstream column is a static read: nothing was compiled or tested.

| Function | Header | OSE status | Upstream libc370 status | Test IDs | Notes |
|---|---|---|---|---|---|
| rename | stdio.h | absent | implemented | — | ISO C |
| getenv, setenv, unsetenv | stdlib.h | absent | implemented | — | `getenv` is also declared in mvs/env.h:19 (corrected after review round 1) |
| time | time.h | absent | implemented | — | ISO C |
| sleep, usleep | unistd.h | absent | implemented | — | timed ECB / STIMER |
| select | sys/select.h | absent | implemented (sockets) | — | dyn75 socket layer, not general fds |
| signal | signal.h | absent | implemented (C89 table only) | — | no async delivery; no sigaction |
| open, close, read, write, lseek, creat, dup, dup2, pipe, fdopen, fileno, isatty, ftruncate, fsync | — | absent | absent | — | no fd layer; candidate backend libc370 + libufs (OSE-005) |
| stat, fstat, mkdir, rmdir, unlink, opendir, readdir, closedir, getcwd, chdir, access, chmod, fchmod, chown, umask, link, symlink, readlink, utime | — | absent | absent | — | no sys/stat.h or dirent.h |
| fork, vfork, exec*, posix_spawn, spawn, wait, waitpid, kill, sigaction | — | absent | absent | — | spec: spawn-first; fork deferred (§1) |
| getpid, getppid, getuid, geteuid, getgid, getegid | — | absent | absent | — | depends on the OSE-007 identity model |
| errno / ENOSYS | errno.h | — | present (140 values, ENOSYS = 38) | — | non-Linux numbering; `errno` is `*(__errno())` |

## Utilities

| Utility | Built-in / external | Status | Test IDs | Notes |
|---|---|---|---|---|
| pwd, cd, ls, cat, echo, mkdir, rm, cp, exit, hello | M1 scope | absent | | |

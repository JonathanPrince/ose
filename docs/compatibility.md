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

OSE-012 seeds this table from the LIBC/370 audit. Nothing is offered by OSE yet.

| Function | Header | OSE status | Upstream libc370 status | Test IDs | Notes |
|---|---|---|---|---|---|

## Utilities

| Utility | Built-in / external | Status | Test IDs | Notes |
|---|---|---|---|---|
| pwd, cd, ls, cat, echo, mkdir, rm, cp, exit, hello | M1 scope | absent | | |

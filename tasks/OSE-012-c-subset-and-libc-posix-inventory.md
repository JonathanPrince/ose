# OSE-012 — Target C subset and LIBC/370 POSIX inventory
Status: BACKLOG (READY after OSE-002 pins cc370 and libc370)
Milestone: M0
Dependencies: OSE-002; the compile probes run with the OSE-004 harness
Owner:
Risk: low
Model tier: economy (inventory extraction); standard for review and the dialect probes
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-012-libc-inventory
Guest resources: none for the inventory; the probes reuse an OSE-004 lease
Baseline commit:
Origin: added by the OSE-001 coordinator. It covers the spec §10 M0 question "target C subset" and the spec §2 direction for LIBC/370: "Audit existing POSIX functions before extending". BOOTSTRAP.md had no card for either.

## Goal and non-goals
Goal: a machine-checkable inventory of the POSIX-relevant headers and functions in libc370 at the pin, each with a status (implemented / stub / absent) and a file:line reference. Plus a small set of compile probes that establish which C constructs CC/370 accepts.
Non-goals: implementing or patching libc functions.

## Inputs and primary references
libc370 and cc370 at their pins; their manuals on mvslovers.readthedocs.io; spec §3.3, §3.5, §3.6; the OSE-005 libufs API list.

## Allowed files / interfaces
`docs/research/YYYY-MM-DD-libc370-inventory.md`, `docs/research/data/libc370-functions.json`, `tests/host/c-probes/*.c` (probe sources only), the POSIX table in `docs/compatibility.md` (upstream column only), this card.

## Acceptance tests (commands and expected outcomes)
1. The JSON parses. Every entry has `name`, `header`, `status`, `source` (`path:line@sha`). The reviewer re-derives 10 random entries from the source.
2. It covers at least the functions M1 and M2 need: open, close, read, write, lseek, stat, fstat, mkdir, rmdir, unlink, rename, opendir, readdir, closedir, getcwd, chdir, getenv, setenv, errno values, pipe, dup, dup2, the exec*/spawn family, waitpid, getpid, getuid, getgid, time, and stdio on file descriptors.
3. Each compile probe records the command, RC and diagnostics (C89 baseline, `long long`, designated initializers, `//` comments, variadic macros, `static inline`, struct packing and alignment). Probe results are `observed`, or marked not-run.

## Escalation triggers
The probes show a construct needed by spec §3.2 (fixed-width types, explicit packing) is unavailable → escalate to OSE-010.

## Handoff
- Changed files / commits:
- Commands run, RC, evidence paths:
- Tests not run and why:
- Decisions / ADRs:
- Known defects / blockers:
- Next action:
- Usage/cost if available:
## Independent review and gate result

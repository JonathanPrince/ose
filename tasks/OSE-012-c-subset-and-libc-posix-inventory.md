# OSE-012 — Target C subset and LIBC/370 POSIX inventory
Status: IMPLEMENTED (review round 1: changes requested 2026-11-26; rework done, probes run, awaiting re-review)
Milestone: M0
Dependencies: OSE-002; the compile probes run with the OSE-004 harness
Owner: coordinator session (2026-11-26)
Risk: low
Model tier: economy (inventory extraction); standard for review and the dialect probes
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-012-libc-inventory
Guest resources: none for the inventory; the probes reuse an OSE-004 lease
Baseline commit: 5970f87
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
- Changed files (branch `task/OSE-012-libc-inventory`, base `5970f87`):
  - `docs/research/2026-11-26-libc370-inventory.md` (new)
  - `docs/research/data/libc370-functions.json` (new: 61 functions, errno summary, 2.29.2 comparison)
  - `tests/host/c-probes/` (README plus 8 probes p01–p08)
  - `docs/compatibility.md` (POSIX table, upstream column)
  - `docs/research/README.md` (index), this card, `docs/status.md`, `tasks/usage.jsonl`
- Commands run, RC, evidence (2026-11-26, Windows 11, Git Bash, Python 3.14.4):
  - `git init` and `git config core.autocrlf false`, then `git fetch --depth 1 https://github.com/mvslovers/libc370 fcde4e88…` and checkout into `artifacts/cache/libc370`: RC 0, HEAD = fcde4e88. Same for `70e450f5` (2.29.2) into `artifacts/cache/libc370-head`.
  - The inventory script (prototype and definition scan) was run twice: the first pass had a regex defect (see the research note L-1), the second is the recorded result. `signal` was corrected by hand.
  - Whole-word cross-check of all 53 "absent" names over `include/ src/ sdk/`: no declaration or definition found.
  - `grep` of `include/errno.h`: 140 defines; ENOSYS = 38.
  - The same scan on 2.29.2 gives an identical classification, and `unistd.h` is unchanged.
  - `python -I scripts/check_repo.py` and `python -I -m unittest discover -s tests/host`: see the usage log entry for this attempt.
- Acceptance status:
  1. JSON parses; every entry has `name`, `header`, `status`, and `source` as `path:line@sha` or null for absent. **Reviewer to re-derive 10 random entries.**
  2. pass: covers every function the card lists, plus 20 related ones (61 in total).
  3. **met after rework:** nine probes compiled and assembled with the pinned cc370 1.6.3 (OSE-004 harness, branch `task/OSE-004-hello-harness` 419fa79). Commands, RCs and diagnostics are in the research note §Probes, with evidence in `artifacts/evidence/ose-012/probes/`. All are `observed`.
- Tests not run and why: runtime behaviour of the probed constructs, which needs a guest (OSE-004 guest part). No guest work in this card, by design.
- Decisions / ADRs: none. The research note L-4 lists hypotheses for OSE-010: OSE must build the POSIX layer itself, probably over libufs.
- Known defects / blockers:
  - Acceptance 3 depends on OSE-004.
  - Static scan only: macros generated at build time or definitions in assembler outside `src/` would be missed. The cross-check found no sign of either.
- Next action: independent standard-tier review of 1–2. Run the probes once OSE-004's toolchain exists (either task may do it, but record it here).
- Usage/cost: not available to the agent.
## Independent review and gate result

### Review round 1 (2026-11-26, relayed by the human): changes requested
- **P2, probes:** accepted.
  - `p04_variadic_macros.c` had a raw newline inside its string literal. Fixed.
  - The C89 baseline probe was missing. Added `p00_c89_baseline.c`.
  - All nine probes were then run with the pinned toolchain. p00 gives RC 0, also with `-std=c89 -pedantic-errors`. p01–p07 give RC 0. p08 gives RC 1 in the default C89 mode and RC 0 with `-std=c99`. The OSE-010 escalation trigger does not fire.
- **P2, environment-function headers:** accepted. The scanner matched names inside comments (`mvs/env.h:32-33`).
  - Fix: strip comments before matching, and prefer the POSIX header. Regenerated the JSON: exactly `getenv`, `setenv` and `unsetenv` changed, now `include/stdlib.h:97/98/100`, with `getenv` also at `mvs/env.h:19`. No status changed.
  - Also corrected the research note's L-1 table and the compatibility table's Header cell. The card's allowed scope is the upstream column, so I note that the Header cell was edited too, to fix the same defect.
- The probe `README.md` result column was updated as well.

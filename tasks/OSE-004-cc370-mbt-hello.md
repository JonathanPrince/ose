# OSE-004 — CC/370 + MBT hello compile/deploy harness
Status: READY (host part; OSE-002 VERIFIED 2026-11-26; guest part needs the OSE-003 image)
Milestone: M0
Dependencies: OSE-002 (host compile); OSE-003 (guest run; a coordination dependency not listed in BOOTSTRAP)
Owner:
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-004-hello-harness
Guest resources: lease required for deploy and run
Baseline commit:

## Goal and non-goals
Goal: compile and link a C "hello" on the host with the pinned CC/370 and MBT (spec §2 prefers host compilation). Deploy the load module to the guest, run it as a batch job and as a TSO command, and capture RC and output automatically. Record the observed C dialect and linkage facts.
Non-goals: POSIX functions, UFSD access, a new toolchain.

## Inputs and primary references
mvslovers/cc370, libc370 and mbt at their pins, and their docs at mvslovers.readthedocs.io. How MBT deploys to the guest must come from MBT source and docs. Do not assume a transport. If it uses FTPD or mvsMF, say so, because OSE-007 treats those as alternate access paths.

## Allowed files / interfaces
`Makefile` (build, deploy), `scripts/build.sh`, `scripts/deploy.sh`, `src/utils/hello/` (test program only), `jcl/hello/*`, `tests/guest/hello/*`, `docs/runbooks/hello-compile-deploy.md`, `docs/research/YYYY-MM-DD-toolchain.md`, this card.

## Acceptance tests (commands and expected outcomes)
1. `make build` → RC 0. Record the toolchain version string and the sha256 of the object and the load module.
2. `make deploy` → RC 0. The member's presence on the guest is confirmed by a listing job, not by the deploy tool's exit code.
3. Batch run: the step RC equals the program's return value (test a planted value such as 4 as well as 0), and the output DD contains the exact expected string. Both are parsed from spool.
4. A TSO invocation shows the same output.
5. Toolchain note covering: compiler version, C dialect observations (C89 features, `long long`, inline asm, varargs), entry linkage, AMODE/RMODE of the output, reentrancy options, and the EBCDIC code page in use. Each item is labeled observed or documented.

## Escalation triggers
- The compiler cannot handle a construct that OSE-012 marks as required → record it and escalate to OSE-010. The spec §5 gate says to adapt the source, not replace the toolchain.
- Runtime ABEND → record the completion code and PSW; escalate after two failed attempts.

## Handoff
- Changed files / commits:
- Commands run, RC, evidence paths:
- Tests not run and why:
- Decisions / ADRs:
- Known defects / blockers:
- Next action:
- Usage/cost if available:
## Independent review and gate result

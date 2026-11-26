# OSE-004 — CC/370 + MBT hello compile/deploy harness
Status: READY (host part IMPLEMENTED 2026-11-26, awaiting review; acceptance 2-4 need the OSE-003 guest, a lease and a deploy-transport decision)
Milestone: M0
Dependencies: OSE-002 (host compile); OSE-003 (guest run; a coordination dependency not listed in BOOTSTRAP)
Owner: author model (standard tier)
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-004-hello-harness
Guest resources: lease required for deploy and run
Baseline commit: 5970f87 (main)

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
  - New: `scripts/build.sh`, `src/utils/hello/hello.c`, `docs/research/2026-11-26-toolchain.md` (with addendum T-7), `docs/runbooks/hello-compile-deploy.md`.
  - Changed: `Makefile` (`build` target), `dependencies.lock.json` (adds `maclib370`, approved by the human 2026-11-26, option a), `docs/research/2026-11-26-licensing.md` (addendum, question 10), the runbook and research indexes, `docs/status.md`, `tasks/usage.jsonl`, this card.
  - Branch `task/OSE-004-hello-harness`: commit 16565eb (blocked state), then the link commit.
- Commands run, RC, evidence paths (all under `artifacts/evidence/ose-004/`):
  - Toolchain: `sh scripts/build.sh toolchain` gave RC 1 three times (missing flex/bison; no git in the image, so no version stamp; libcc370rt not built), then RC 0. Versions `cc370/as370/ld370 1.6.3 (802dde1)`. maclib370 `extract.py --verify`: 1035/1035, RC 0.
  - libc: `sh scripts/build.sh libc` → RC 0, `libc.a` `d3a422e8…`.
  - hello: `sh scripts/build.sh hello` → RC 0, `HELLO` `81757408…`, `HELLO.xmit` `0e69e9fa…`. Byte-identical across runs once the timestamps were pinned (research T-7).
  - **Acceptance 1: `make build` (GNU Make 4.2.1) → RC 0** after a clean rebuild of everything. The same hashes came out twice.
  - Probes: `PROBE_DIR=… sh scripts/build.sh probes` (research T-4).
  - `python scripts/check_repo.py`: RC 0. Host unittest: RC 0.
- Tests not run and why:
  - Acceptance 2–4 (deploy and confirmation listing, batch RC/output with a planted RC 4, TSO run) are not run: no guest (OSE-003), no lease, and the deploy transport is undecided (mbt uses mvsMF over HTTP Basic, an alternate access path for OSE-007).
  - Acceptance 5: compile-time and link-time facts are recorded (T-4, T-5, T-7). The runtime dialect checks need the guest.
- Decisions / ADRs: human decision 2026-11-26: option (a), maclib370 v1.0.0 `e85286a7` added to the lock. No ADR.
- Known defects / blockers:
  - The macros are TK5-derived; that they work on MVS/CE needs a guest run.
  - The licence of the macro content is UNRESOLVED (licensing question 10).
  - The OSE-012 probe `p04` has a raw newline in a string literal; the fix belongs on the OSE-012 branch.
  - Debian packages are not snapshot-pinned.
- Next action: standard-tier review of the host part. After OSE-003: choose a deploy transport, write `scripts/deploy.sh`, `jcl/hello/*` and `tests/guest/hello/*`, then run acceptance 2–4 under a lease.
- Usage/cost if available: not metered.
## Independent review and gate result

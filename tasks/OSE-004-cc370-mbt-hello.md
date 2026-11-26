# OSE-004 — CC/370 + MBT hello compile/deploy harness
Status: BLOCKED (2026-11-26: host build stops at the link; maclib370 is a required dependency that is not in the lock. Human decision needed, see Handoff)
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
- Changed files / commits: `scripts/build.sh` (new), `Makefile` (`build` target), `src/utils/hello/hello.c` (new), `docs/research/2026-11-26-toolchain.md` (new), `docs/runbooks/hello-compile-deploy.md` (new) and the runbook index, `docs/research/README.md`, `docs/status.md`, `tasks/usage.jsonl`, this card. Branch `task/OSE-004-hello-harness`.
- Commands run, RC, evidence paths (all under `artifacts/evidence/ose-004/`):
  - `docker pull debian:bookworm-slim` → `debian@sha256:e67eeead…` (pinned in `scripts/build.sh`).
  - `sh scripts/build.sh toolchain`: RC 1 twice (missing flex/bison, then no git in the image while adding the version stamp), then RC 0. Versions `cc370/as370/ld370 1.6.3 (802dde1)`. Logs in `cc370-build.log`, `versions.txt`, `apt-versions.txt`.
  - `PROBE_DIR=… sh scripts/build.sh probes`: RC 0. p01–03 and p05–07 RC 0. p04 RC 1 (probe defect) and p08 RC 1 (C89 default); see `probes/` and `probes-extra/`.
  - `sh scripts/build.sh hello`: RC 3. `hello.s` and `hello.o` were built; their sha256 is in `hello/sha256.txt`, and `hello.o` is identical across two toolchain builds.
  - libc370 `make` without maclib370: RC 2 (`libc370-build-without-maclib370.txt`).
  - `python scripts/check_repo.py`: RC 0. `python -m unittest discover -s tests/host`: RC 0.
- Tests not run and why:
  - Acceptance 1 (`make build` RC 0 with a load module) is **blocked**: no `libc.a` without maclib370. `make` is also not installed on the Windows host; it is available in the container.
  - Acceptance 2–4 (deploy, batch, TSO) are not run: blocked by the link, by the absent OSE-003 guest and lease, and by the transport decision (research T-6, mvsMF).
  - Acceptance 5: compile-time parts are recorded (T-4, T-5). AMODE/RMODE and reentrancy are open until a link.
- Decisions / ADRs: none taken. **Human decision requested:** (a) approve maclib370 v1.0.0 `e85286a7` into the lock (macro content license UNRESOLVED, TK5-derived); (b) derive the macros from the pinned MVS/CE image instead; or (c) lock the prebuilt libc370 2.25.1 sysroot asset. Details and trade-offs: research T-1.
- Known defects / blockers:
  - maclib370 (above).
  - The OSE-012 probe `p04_variadic_macros.c` contains a raw newline in a string literal. The fix belongs on the OSE-012 branch.
  - Debian packages are not snapshot-pinned.
- Next action: the human chooses an option for T-1. Then add the lock entry, implement the link stage in `scripts/build.sh`, and record the load-module sha256 and `file370 -v` attributes. Guest steps follow OSE-003.
- Usage/cost if available: not metered.
## Independent review and gate result

# OSE-003 — Build host doctor and Sysgen wrapper; native TSO/JES smoke
Status: READY (2026-11-26: ADR-0003 accepted, option A; OSE-013 VERIFIED and merged. Follow upstream/sysgen/MANIFEST.md steps 1-3b, including sysgen --keep-temp)
Milestone: M0
Dependencies: OSE-002; OSE-013 (added in the OSE-002 rework); ADR-0003 (accepted). Clone all caches with `core.autocrlf=false` (research sysgen-pins P-9)
Owner:
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-003-build-host-sysgen
Guest resources: lease required (creates the first DASD set)
Baseline commit:

## Goal and non-goals
Goal: build MVS/CE from a clean checkout with the pinned Sysgen and Hercules, as a non-root user, on the build host chosen in ADR-0003. IPL it twice and prove that native JES2 and TSO work, with every check parsed automatically.
Non-goals: OSE code, UFSD tests, the snapshot/lease tooling (OSE-009), performance tuning.

## Inputs and primary references
ADR-0003, ADR-0004, `dependencies.lock.json`, the sysgen README at the pin (recon R-05: Debian/Ubuntu only, never as root, 30-minute default timeout), sysgen `tests/`, wrljet/hercules-helper at its pin. **Reuse the upstream sysgen test and automation scripts before writing new ones.**

## Allowed files / interfaces
`Makefile` (targets doctor, fetch, sysgen), `scripts/doctor.sh`, `scripts/sysgen.sh`, `scripts/lib/*`, `scripts/host/*` (container or WSL provisioning), `sysgen/` (wrapper config, empty customize fragment), `jcl/smoke/*.jcl`, `tests/integration/smoke/*`, `docs/runbooks/build-host.md`, `docs/runbooks/sysgen-and-ipl.md`, this card.

## Acceptance tests (commands and expected outcomes)
1. `make doctor` on a fresh host → RC 0. It checks the OS, that it is not running as root, the Hercules version against the lock, Python, free disk space and free ports. A failing check gives a nonzero RC and a message (demonstrate at least one failure).
2. `make fetch && make sysgen` from a clean checkout → RC 0 and a DASD set under `artifacts/`. Record the elapsed time and the sha256 of the logs.
3. Two cold IPLs of the result. Both console logs show IPL completion and JES2 initialized. The runbook records the exact message IDs taken from the observed log.
4. JES2 smoke job (IEFBR14 plus a step with a planted nonzero RC). The host script parses each step RC from spool: expected 0000 and the planted value. Submission success alone does not count.
5. TSO smoke: automated logon as a non-admin user, one command with checked output, then logoff. Use upstream tooling if it exists; otherwise use pinned s3270 scripting.
6. A second agent or person repeats steps 1–4 using only the runbook.
7. **Pin enforcement end to end** (moved here from OSE-013 on 2026-11-26 to remove a circular gate). The `make sysgen` run of test 2 uses OSE-013's patch and check. Its log shows MVP at `4c004a59…` and RAKF at `941b07dc…`, and the MVP package hashes match the lock. Also run once with a deliberately wrong MVP pin and show that sysgen stops with a nonzero RC before the MVP install. Then remove the `pending_enforcement` entries from the lock, citing this test's evidence.

## Escalation triggers
- The Hercules or sysgen deadlock happens twice → BLOCKED with logs.
- Container networking or timing problems → try ADR-0003 option B and record both outcomes.
- Any step needs root → stop.

## Handoff
- Changed files / commits:
- Commands run, RC, evidence paths:
- Tests not run and why:
- Decisions / ADRs:
- Known defects / blockers:
- Next action:
- Usage/cost if available:
## Independent review and gate result

# OSE-013 — Enforce the MVP and RAKF pins in the Sysgen build
Status: READY (approved 2026-11-26; OSE-002 VERIFIED)
Milestone: M0
Dependencies: OSE-002 (pins recorded in `dependencies.lock.json`)
Owner:
Risk: medium (reproducibility of every later guest result)
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-013-enforce-pins
Guest resources: none for the patch and host tests; the end-to-end check reuses the OSE-003 sysgen run under its lease
Baseline commit:
Origin: created during the OSE-002 rework (review finding 3, 2026-11-26). On 2026-11-26 the human split the work: OSE-002 records the pins and this card enforces them. This card closes the lock's `pending_enforcement` entries.

## Goal and non-goals
Goal: make a Sysgen build fail closed unless MVP is exactly `4c004a599f6a49442fade63cdb3cc3a9e0fdf58a` and RAKF is exactly `941b07dc19adb7a1a153caaeba96b659ff2ad3e0`. Do it with the smallest reviewable change: patch P-01 in `upstream/sysgen/MANIFEST.md`, kept as `upstream/sysgen/patches/0001-*.patch`, plus the OSE wrapper check.
Non-goals: changing which MVP packages are installed; bumping any version; offering the patch upstream (outreach needs human approval).

## Inputs and primary references
- `dependencies.lock.json`: `mvp`, `rakf`, `pending_enforcement`.
- `docs/research/2026-11-26-sysgen-pins.md`: P-1, P-7 and the addendum (MVP packages; Windows `core.autocrlf`).
- sysgen@4746195d: `sysgen.py` l.2113 (RAKF clone), l.2734 (MVP clone), l.3210–3270 (`git_clone`), `mvslovers.conf` `[rakf]`.

## Allowed files / interfaces
`upstream/sysgen/patches/0001-*.patch`, `upstream/sysgen/MANIFEST.md`, `scripts/lib/pins.*` (check helper), `tests/host/test_pins*.py`, this card. The `sysgen.sh` wrapper belongs to OSE-003; coordinate with it, do not edit it here.

## Acceptance tests (commands and expected outcomes)
1. The patch applies cleanly to sysgen@4746195d (`git apply --check`), and its diff is ≤ 40 lines excluding context.
2. Host test: with the patch, `git_clone()` given an MVP ref checks out exactly that SHA, both on a fresh clone and when a stale clone already exists.
3. Host test: a post-clone check compares `git rev-parse HEAD` with the lock for MVP and RAKF and exits nonzero, naming the component, on a mismatch. Demonstrate the failure with a deliberately wrong SHA.
4. Host test: every MVP package file in the clone hashes to the lock's `mvp-pkg-*` sha256, measured on the git blob or a clone made with `core.autocrlf=false`. A clone with CRLF-converted text packages must be detected and rejected.
5. The patch and the check helper are packaged for OSE-003 to call: a documented interface (command, arguments, exit codes) in `upstream/sysgen/MANIFEST.md`.
6. Update each `pending_enforcement` entry in the lock to `"status": "host-verified"` and cite the host test IDs. **Do not remove the entries.** OSE-003 removes them after its end-to-end run (OSE-003 acceptance test 7).

Completion boundary (added 2026-11-26 to fix the circular gate found in the OSE-002 re-review): this card finishes on **host-verified** enforcement, tests 1–6, with no guest or full sysgen run. The end-to-end proof that a real sysgen build used the pinned SHAs belongs to OSE-003. That keeps the order acyclic: OSE-002 → OSE-013 → OSE-003.

## Escalation triggers
The patch needs more than a minimal change to sysgen → stop and propose an alternative, such as a pre-staged clone plus a sysgen option. Sysgen behaves differently from what was read at l.3210–3270 → record it and escalate.

## Handoff
- Changed files / commits:
- Commands run, RC, evidence paths:
- Tests not run and why:
- Decisions / ADRs:
- Known defects / blockers:
- Next action:
- Usage/cost if available:
## Independent review and gate result

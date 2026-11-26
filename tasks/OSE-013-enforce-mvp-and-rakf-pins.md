# OSE-013 — Enforce the MVP and RAKF pins in the Sysgen build
Status: IMPLEMENTED (review round 1: changes requested 2026-11-26; rework done, awaiting re-review)
Milestone: M0
Dependencies: OSE-002 (pins recorded in `dependencies.lock.json`)
Owner: coordinator session (2026-11-26)
Risk: medium (reproducibility of every later guest result)
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-013-enforce-pins
Guest resources: none for the patch and host tests; the end-to-end check reuses the OSE-003 sysgen run under its lease
Baseline commit: 5970f87
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
- Changed files (branch `task/OSE-013-enforce-pins`, base `5970f87`):
  - `upstream/sysgen/patches/0001-pin-mvp-and-rakf-commits.patch`: P-01, 40 changed lines in `mvslovers.conf`, `mvslovers.py` and `sysgen.py`.
  - `upstream/sysgen/MANIFEST.md`: patch table plus the OSE-003 interface.
  - `scripts/lib/pins.py`: `check-clone` and `check-mvp-packages`.
  - `tests/host/test_pins.py`: T-PIN-001…008 (008 added in review rework).
  - `dependencies.lock.json`: `pending_enforcement` set to `status: host-verified`, with the test IDs and the remaining OSE-003 step.
  - Removed the empty skeleton directory `upstream/patches/` (patches live per component under `upstream/<component>/patches/`, as `upstream/README.md` says).
  - This card, `docs/status.md`, `tasks/usage.jsonl`.
- Design: a new `commit` key next to `ref`. Overloading `ref` would not work, because a fresh `git clone --branch <sha>` fails and `update_manifest` would query MVP's non-existent releases.
  - `git_clone(commit=…)` checks the commit out on both the fresh-clone and existing-clone paths, then `git_verify_commit` compares `rev-parse HEAD` with the pin and raises on a mismatch.
  - `update_manifest` skips commit-pinned entries (logged "move it by hand"). Its report loop now iterates `new`; iterating `products` would have raised KeyError for skipped entries.
  - RAKF keeps `ref = v2.1.0` (the log message and the RAKFINST expectations are unchanged) and gains `commit = 941b07dc…`.
- Commands run, RC, evidence (2026-11-26, Windows 11, Git Bash, Python 3.14.4):
  - LF-safe upstream checkout: `git -c core.autocrlf=false clone --no-checkout artifacts/cache/sysgen artifacts/cache/sysgen-lf` and `checkout 4746195d…`. RC 0.
  - Upstream suite **before** the patch: `python -m unittest discover -s tests` (in sysgen-lf) → 60 tests, 1 error, 10 skipped. The error is `DlmTest.test_record_size_checked`, which reopens an open NamedTemporaryFile and fails only on Windows. Pre-existing and unrelated.
  - Upstream suite **after** the patch → the same 60 / 1 (same test) / 10. No regressions.
  - Changed-line count of the patch: 40 (first draft 42, two config comments trimmed).
  - `python -I -m unittest discover -s tests/host -v` → 18 tests OK, RC 0: T-PIN-001…007 plus the 11 repo-check tests. First runs failed for test-harness reasons that are now fixed: importing `sysgen.py` executes `main()`, a Windows path was passed where a URL-style path was expected, and the empty-line count bug in T-PIN-001. No patch logic changed between the failing and the passing run.
  - `python -I scripts/check_repo.py` → OK, RC 0.
- Acceptance status:
  1. pass (T-PIN-001: `git apply --check` RC 0; 40 ≤ 40).
  2. pass (T-PIN-002 fresh clone; T-PIN-003 existing stale clone, including the unchanged unpinned pull path).
  3. pass. Failure demonstrated in T-PIN-004 (patched sysgen refuses an unreachable commit, fresh and existing) and T-PIN-006 (`pins.py` exits 1 naming `rakf:` on a wrong pin, and 2 for an unknown component).
  4. pass (T-PIN-007: an autocrlf=false clone passes all 22 package hashes; an autocrlf=true clone fails, naming `mvp-pkg NJE38` and the remedy).
  5. pass (interface documented in `upstream/sysgen/MANIFEST.md`).
  6. pass (both entries `host-verified` with test IDs, not removed).
- Tests not run and why:
  - No real sysgen run or network clone of MVP or RAKF; that is OSE-003 test 7 by design.
  - The patched `git_clone` was exercised against local repositories, not GitHub.
  - Not tested on Linux yet. The expected clone paths `temp/RAKF` and `MVSCE/MVP` were derived from code, not observed.
- Hazards for OSE-003 and reviewers:
  - `sysgen.py` calls `main()` at module level (l.3575). Never import it.
  - Windows `which git` returns an MSYS path.
  - CRLF clones corrupt MVP packages.
  - All three are recorded in `upstream/sysgen/MANIFEST.md`.
- Decisions / ADRs: none new. P-01 follows ADR-0004 §4 (small reviewable patch, offered upstream later) and ADR-0005 §3.
- Known defects / blockers: none known. Offering P-01 upstream needs human approval (outreach).
- Next action: independent standard-tier review (rerun the host tests with the caches present, read the patch). Then OSE-003 uses the interface and closes the lock entries in its test 7.
- Usage/cost: not available to the agent.
## Independent review and gate result

### Review round 1 (2026-11-26, relayed by the human): changes requested
- **P2, validation after consumption:** accepted. The handoff sequence ran sysgen and checked the package hashes afterwards, but step 9 clones MVP and installs it in one go, so corrupted bytes could be installed before they were rejected. Rework:
  - `upstream/sysgen/MANIFEST.md` interface steps 2–3b now pre-stage the RAKF and MVP clones at their pins (LF-safe, at the paths sysgen uses) and validate them with `pins.py` **before** sysgen starts. The patched `git_clone` reuses the validated tree; a post-run check stays as evidence only.
  - New host test **T-PIN-008**: a corrupted pre-staged package is rejected; a valid tree passes, is reused unchanged by the patched `git_clone` (no re-clone, `HEAD` at the pin), and passes again afterwards. `python -m unittest tests.host.test_pins`: 8 tests, RC 0.
  - Lock `pending_enforcement` now cites T-PIN-001..008. The patch itself is unchanged (still 40 lines, T-PIN-001).

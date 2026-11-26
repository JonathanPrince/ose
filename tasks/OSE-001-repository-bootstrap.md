# OSE-001 — Initialize repository, docs, task schema, CI skeleton
Status: REVIEW
Milestone: M0
Dependencies: none
Owner: bootstrap coordinator (agent session, 2026-11-26)
Risk: low
Model tier: economy per BOOTSTRAP. In practice the high-tier coordinator did it, together with the M0 decomposition
Reviewer tier: standard or human
Budget: local-only
Branch: main (the repository had no commits; the human makes the first commit)
Guest resources: none
Baseline commit: none (repository initialized by this task)

## Goal and non-goals
Goal: create the spec §4 layout, shared docs, ADR and task conventions, the M0 cards and a local, vendor-neutral consistency check.
Non-goals: any build, guest or OSE code; architecture ADRs.

## Inputs and primary references
AGENTS.md, spec/OSE-SPEC.md (moved from the repo root as AGENTS.md instructed), tasks/BOOTSTRAP.md, tasks/TEMPLATE.md.

## Allowed files / interfaces
Everything outside `src/` and `include/` content (placeholders only there).

## Acceptance tests (commands and expected outcomes)
1. `python3 scripts/check_repo.py` → RC 0 (required files, card fields and statuses, ADR headers, lock and usage JSON).
2. `python3 -m unittest discover -s tests/host` → RC 0 (tests of the checker itself, including negative cases).
3. A fresh clone contains AGENTS.md, spec/OSE-SPEC.md and docs/status.md, and every link in README.md resolves (the checker verifies relative links in README.md, AGENTS.md and docs/status.md).
4. No vendor requirement: the checks use only the Python standard library. The GitHub workflow merely calls the same script.

## Escalation triggers
None hit.

## Handoff
- Changed files / commits: whole tree (uncommitted). `OSE-SPEC.md` moved to `spec/`. AGENTS.md path reference updated (the only edit to the operating contract). Spec text unchanged.
- Commands run, RC, evidence paths: read-only GitHub API and raw-file queries for 13 upstream repositories (results in docs/research/2026-11-26-upstream-recon.md). Local tool inventory (recon R-07). Verification on 2026-11-26 (Windows 11, Git Bash, Python 3.14.4): `python -I scripts/check_repo.py` → "check_repo: OK", RC 0. `python -I -m unittest discover -s tests/host -v` → 10 tests OK, RC 0 (8 negative cases among them).
- Tests not run and why: CI workflow not exercised (no remote; publishing a remote needs human permission).
- Decisions / ADRs: ADR-0001 to 0004 proposed. New cards OSE-011 and OSE-012 proposed.
- Known defects / blockers: `make` is not installed on the Windows workstation, so the Makefile is untested there; it targets the Linux build host (ADR-0003). Run the checker directly with python.
- Next action: human review, initial commit, decisions listed in docs/status.md.
- Usage/cost if available: not available to the agent (recorded as null in tasks/usage.jsonl).
## Independent review and gate result
Pending.

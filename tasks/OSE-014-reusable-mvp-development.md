# OSE-014 — Extract reusable MVS/CE MVP package development environment
Status: BACKLOG
Milestone: M0 follow-up (independent export gate, spec §5.1)
Dependencies: OSE-010 M0 gate; accepted build/deploy/evidence harness and recovery work (OSE-003, OSE-004, OSE-009)
Owner: unassigned
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only unless explicitly approved
Branch: task/OSE-014-reusable-mvp-development
Guest resources: lease required for package installation and guest tests
Baseline commit: unassigned until claim

## Goal and non-goals
Extract the independently verified development foundation into a separate repository suitable as a base for other MVS/CE MVP package projects. OSE uses the same foundation. Implement spec §§1.1, 4.1 and 5.1. Do not build another package manager or require OSE runtime services. Repository creation/publication and releases remain a later human-approved action.

## Inputs and primary references
Spec §§2, 4–6, 8–9; ADRs 0002–0006; dependencies.lock.json; OSE-003/004/009 runbooks and review evidence. Verify the MVP package format and installation path from the pinned MVP sources. XMIT RECEIVE by itself is not MVP acceptance.

## Allowed files / interfaces
Extraction manifest and staging tree under ignored artifacts; shared build/deploy/test harness, example package layout, packaging recipes, relevant runbooks, spec references and this card. Agree the concrete file set and versioned consumption interface when claiming; any new dependency/interface decision needs an ADR. Do not modify OSE runtime behavior as part of extraction.

## Acceptance tests (commands and expected outcomes)
Use spec §5.1 as the acceptance checklist. Record exact commands, RCs, guest configuration, pins and evidence when implemented:
1. Independent clean-checkout build/deploy/batch/TSO/recovery repeat; all expected checks pass and negative paths fail.
2. A real MVP package installs through the documented MVP path on a disposable guest and passes listing/runtime checks; supported repeat installation and recovery are verified.
3. A second independent example works through configuration/package files without shared harness source changes or OSE runtime services.
4. Export manifest, license/provenance review, supported-host matrix, isolated credentials/evidence and redistribution exclusions checked.
5. Independently validated extracted tree; foundation version/maintenance and OSE consumption plan documented; human selects repository destination and release/publication decision.

## Escalation triggers
Uncertain MVP install semantics or redistribution rights; new dependency; interface/versioning decision; privileged guest behavior; failed independent review. No publication until the human approves its concrete contents and destination.

## Handoff
- Changed files / commits: specification amendment and this follow-up card added on 2026-11-27 at the user's request; extraction not started.
- Commands run, RC, evidence paths: `python -I scripts/check_repo.py` -> RC 0; `git diff --check` -> RC 0 for the specification amendment. These validate documentation structure only.
- Tests not run and why: all export/guest/package acceptance tests; task is BACKLOG pending the foundation and M0 gate.
- Decisions / ADRs: user direction 2026-11-27 to reuse the development environment as a separate base repository for other MVP package projects. No new dependency or ABI selected.
- Known defects / blockers: current build/deploy review findings must be closed; MVP package workflow and second-project reuse still need demonstration.
- Next action: finish M0; then claim this card, agree extraction file set and implement/test spec §5.1 before publication.
- Usage/cost if available: not metered.

## Independent review and gate result
Pending; no claim that export acceptance has passed.

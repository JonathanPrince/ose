# OSE-014 — Reusable MVP development platform, export and M0a gate
Status: BACKLOG
Milestone: M0a (first deliverable, spec §5.1)
Dependencies: OSE-009 VERIFIED or MERGED; accepted inventory, pins and build/deploy/toolchain baseline (OSE-002, OSE-003, OSE-004, OSE-012, OSE-013). No OSE-010/006/007/008 dependency.
Owner: unassigned
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only unless explicitly approved
Branch: task/OSE-014-reusable-mvp-development
Guest resources: lease required for package installation and guest tests
Baseline commit: unassigned until claim

## Goal and non-goals
Generalize and independently verify the existing build/deploy/test tooling, add a real MVP package workflow and package project configuration, and extract the development foundation into a separate repository suitable as a base for other MVS/CE MVP package projects. OSE uses the same foundation. Implement spec §§1.1, 4.1 and 5.1. Do not build another package manager or require OSE runtime services. Repository creation/publication and releases remain a later human-approved action.

## Inputs and primary references
Spec §§2, 4–6, 8–9; ADRs 0002–0006; dependencies.lock.json; OSE-003/004/009 runbooks and review evidence. Verify the MVP package format and installation path from the pinned MVP sources. XMIT RECEIVE by itself is not MVP acceptance.

## Allowed files / interfaces
Extraction manifest and staging tree under ignored artifacts; shared build/deploy/test harness, example package layout, packaging recipes, relevant runbooks, spec references and this card. Select concrete source/test paths within that scope and document the versioned consumption interface when claiming; any new dependency/interface decision needs an ADR. Do not modify OSE runtime behavior as part of extraction.

## Acceptance tests (commands and expected outcomes)
Use spec §5.1 as the acceptance checklist. Record exact commands, RCs, guest configuration, pins and evidence when implemented:
1. Independent clean-checkout build/deploy/batch/TSO/recovery repeat; all expected checks pass and negative paths fail.
2. A real MVP package installs through the documented MVP path on a disposable guest and passes listing/runtime checks; supported repeat installation and recovery are verified.
3. A second independent MVP example builds, packages, installs and passes guest checks through configuration/package files without shared harness source changes or OSE runtime services.
4. Export manifest, license/provenance review, supported-host matrix, isolated credentials/evidence and redistribution exclusions checked.
5. Independently validated standalone extracted tree with no private cache or OSE checkout/runtime dependency; foundation version/maintenance and OSE consumption plan documented.
6. Independent reviewer signs all spec §5.1 results; human accepts M0a in this card before OSE-006/007/008 start. Repository destination, publication and release remain separate human decisions; no published repository is required to establish the technical gate.

## Escalation triggers
Uncertain MVP install semantics or redistribution rights; new dependency; interface/versioning decision; privileged guest behavior; failed independent review. No publication until the human approves its concrete contents and destination.

## Handoff
- Changed files / commits: specification amendment and this follow-up card added on 2026-11-27 at the user's request; extraction not started.
- Commands run, RC, evidence paths: `python -I scripts/check_repo.py` -> RC 0; `git diff --check` -> RC 0 for the specification amendment. These validate documentation structure only.
- Tests not run and why: all export/guest/package acceptance tests; task is BACKLOG pending OSE-009 acceptance; it does not wait for the OSE-specific M0b gate.
- Decisions / ADRs: user direction 2026-11-27 to reuse the development environment as a separate base repository for other MVP package projects. No new dependency or ABI selected.
- Known defects / blockers: OSE-003/004 build/deploy findings are closed in merged work; generic isolation/recovery, the MVP package workflow, second-project reuse and standalone export still need demonstration.
- Next action: complete and accept OSE-009; then claim this card, generalize the harness, implement/test MVP packaging and the two examples, validate the standalone export, and obtain M0a review/human gate acceptance before new OSE-specific tasks.
- Usage/cost if available: not metered.

## Independent review and gate result
Pending; no claim that export acceptance has passed.

### Platform-first amendment — 2026-11-27
The human moved this deliverable ahead of remaining OSE-specific work. OSE-014 is no longer a post-OSE-010 follow-up: it owns the M0a technical gate and depends only on generic baseline/recovery work. Configuration must move package-specific names, data sets, credentials selection, artifact pins and expected output out of shared code; generic command defaults must operate on a selected package project. The existing HELLO recipe becomes an example/consumer, and the second example proves reuse. New dependencies or a selected public interface still require an ADR when designed. No implementation or export acceptance is claimed by this planning change.

Planning validation for the platform-first amendment: `python -I scripts/check_repo.py` RC 0; `git diff --check` RC 0; inline Python assertions of 009 → 014 → 006/007/008 → 010 dependencies and retained M3/no-host-mock gates RC 0. No implementation/host-suite/guest acceptance tests were run for this documentation and placeholder-label change.

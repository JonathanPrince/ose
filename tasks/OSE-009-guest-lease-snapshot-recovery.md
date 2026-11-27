# OSE-009 — Guest lease, snapshot and recovery harness
Status: READY
Milestone: M0a (generic platform)
Dependencies: OSE-003
Owner:
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-009-guest-harness
Guest resources: creates its own disposable images
Baseline commit:

## Goal and non-goals
Goal: tooling that (a) gives each task an isolated guest image with configurable ports, (b) makes it impossible for two mutating tasks to use the same emulator or DASD set at once, and (c) snapshots and restores a known-good DASD set. It must be proven by forced-failure recovery. This replaces the manual `Guest lease:` line in `docs/status.md`.
The harness must use package-neutral guest/volume/port configuration and be usable by both the MVP example projects and OSE, without an OSE runtime service. It is the next implementation priority and feeds OSE-014; no OSE-006/007/008 completion is required.
Non-goals: a general orchestrator (spec §10), cloud hosting.

## Inputs and primary references
OSE-003 runbooks and scripts; Hercules documentation at the pinned version (shadow files, config, ports); spec §4 and §6.

## Allowed files / interfaces
`Makefile` (restore, a lease helper), `scripts/guest/*`, `tests/integration/harness/*`, `docs/runbooks/guest-lease-snapshot-restore.md`, `tasks/README.md` (the guest-resources section, edited only after review), this card.

## Acceptance tests (commands and expected outcomes)
1. Acquiring a lease on a DASD set succeeds. A second acquire on the same set exits nonzero with the holder's identity, and a stale lease (dead holder PID) is detected and reported, not silently stolen.
2. Two images with different ports run at the same time without conflict.
3. Snapshot, IPL, modify the guest, forced kill of Hercules (`kill -9`), restore, IPL → the OSE-003 JES/TSO smoke passes and the modification is gone.
4. A snapshot's sha256 manifest is verified on restore, and a corrupted snapshot is refused.
5. Every command exits nonzero on failure, and logs go to `artifacts/`.

## Escalation triggers
Hercules locking or shadow-file behavior differs from its documentation → record it, and fall back to full copies.

## Handoff
- Changed files / commits:
- Commands run, RC, evidence paths:
- Tests not run and why:
- Decisions / ADRs:
- Known defects / blockers:
- Next action:
- Usage/cost if available:
## Independent review and gate result

### Scheduling amendment — 2026-11-27
Human direction: deliver the generic platform before new OSE-specific work. OSE-003 is merged, so this card is READY. Implement and independently review isolation/recovery first, then use it for OSE-014. Acceptance tests above remain mandatory; existing manual leases remain in force until the replacement is reviewed. No harness acceptance test ran as part of this documentation amendment.

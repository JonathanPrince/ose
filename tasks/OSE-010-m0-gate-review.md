# OSE-010 — M0 gate review and M1 task decomposition
Status: BACKLOG
Milestone: M0b (OSE gate after M0a)
Dependencies: OSE-014 (M0a independently accepted with human gate approval), OSE-001 to OSE-009, OSE-011, OSE-012, OSE-013
Owner: integration owner and human maintainer
Risk: high
Model tier: high and human
Reviewer tier: human (decides)
Budget: local-only
Branch: task/OSE-010-m0-gate
Guest resources: lease for re-running the evidence
Baseline commit:

## Goal and non-goals
Goal: decide whether M0b and therefore the combined M0 pass, by re-running and checking the evidence against each gate criterion in `docs/status.md`. Write the first architecture ADRs and settle the three spec §5 decision gates: the UFSD extension path, toolchain adequacy, and process isolation feasibility. Decompose M1 into cards.
Non-goals: implementing M1.

## Inputs and primary references
All M0 task handoffs, research notes, ADR-0001 to 0004, spec §5 and §10.

## Allowed files / interfaces
`docs/adr/*` (new ADRs), `docs/status.md`, `docs/compatibility.md`, `tasks/OSE-1NN-*.md`, `spec/` (only proposed amendments for the human, such as the RAKF row in §2 and the /home vs /u convention).

## Acceptance tests (commands and expected outcomes)
1. Confirm the earlier M0a acceptance in OSE-014 without making platform delivery depend on this card. Each M0b gate row in `docs/status.md` points to evidence that was re-run, with date, command and RC.
2. Each spec §10 M0 question has a recorded answer or an explicit deferral: exact versions, build host, terminal APIs, target C subset, RAKF baseline, available historical macros, and whether UFSD exposes trustworthy identity.
3. ADRs cover at least the process model direction (or "constrain to single-user"), the UFSD reuse strategy and the identity approach. Each ADR is marked Proposed until the human accepts it.
4. M1 cards follow the template and pass `make check`.

## Escalation triggers
A gate item fails → M0 stays open. The human decides whether to waive it, and spec §5 forbids waiving M3-type security gates.

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
OSE-014 now supplies the earlier generic platform gate. This card retains every OSE-specific M0 decision and M1 decomposition requirement; it consumes M0a acceptance and is not a prerequisite for platform packaging/export. No OSE security gate is waived.

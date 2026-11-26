# OSE-010 — M0 gate review and M1 task decomposition
Status: BACKLOG
Milestone: M0
Dependencies: OSE-001 to OSE-009, OSE-011, OSE-012
Owner: integration owner and human maintainer
Risk: high
Model tier: high and human
Reviewer tier: human (decides)
Budget: local-only
Branch: task/OSE-010-m0-gate
Guest resources: lease for re-running the evidence
Baseline commit:

## Goal and non-goals
Goal: decide whether M0 passes, by re-running and checking the evidence against each gate criterion in `docs/status.md`. Write the first architecture ADRs and settle the three spec §5 decision gates: the UFSD extension path, toolchain adequacy, and process isolation feasibility. Decompose M1 into cards.
Non-goals: implementing M1.

## Inputs and primary references
All M0 task handoffs, research notes, ADR-0001 to 0004, spec §5 and §10.

## Allowed files / interfaces
`docs/adr/*` (new ADRs), `docs/status.md`, `docs/compatibility.md`, `tasks/OSE-1NN-*.md`, `spec/` (only proposed amendments for the human, such as the RAKF row in §2 and the /home vs /u convention).

## Acceptance tests (commands and expected outcomes)
1. Each gate row in `docs/status.md` points to evidence that was re-run, with date, command and RC.
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

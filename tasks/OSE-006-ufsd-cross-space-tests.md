# OSE-006 — UFSD cross-address-space filesystem tests
Status: BACKLOG
Milestone: M0b (after reusable platform gate)
Dependencies: OSE-014 (M0a independently accepted with human gate approval); OSE-003, OSE-004, OSE-005 (OSE-009 strongly preferred for snapshot and restore)
Owner:
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-006-ufsd-tests
Guest resources: lease required; uses a disposable DASD copy only
Baseline commit:

## Goal and non-goals
Goal: show through guest tests that the installed UFSD serves at least two independent clients in separate address spaces correctly and persistently. Also characterize its failure behavior. This covers the M0 gate item "UFSD read/write across two guest clients".
Non-goals: fixing UFSD (record defects as upstream issue drafts), security enforcement (OSE-007 plans it).

## Inputs and primary references
`docs/interfaces/ufsd-observed.md` (OSE-005), the OSE-004 harness, spec §3.3 and §6.

## Allowed files / interfaces
`src/utils/ufstest/` (test programs only), `jcl/ufsd-tests/*`, `tests/guest/ufsd/*`, `tests/fixtures/ufsd/*` (marked binary), `Makefile` (test-guest), `docs/research/YYYY-MM-DD-ufsd-guest-tests.md`, this card.

## Acceptance tests (commands and expected outcomes)
Each test has an ID (`T-UFSD-NNN`), runs as a guest job or TSO session, and has RC and output parsed by `make test-guest`:
1. Client A (batch job, user 1) writes a file and client B (another job or TSO session) reads back identical bytes.
2. A byte round trip of all 256 values plus embedded NULs, compared by sha256 on both sides.
3. Persistence: write, clean shutdown, IPL, read back identical data.
4. Long names, deep paths and directory iteration, with the observed limits recorded.
5. Partial and large writes across record or block boundaries, and append and seek behavior.
6. A full filesystem: the error is reported and nothing is silently truncated.
7. Concurrent writers to the same and to different files: record what happens.
8. UFSD stopped mid-operation, and a client ABEND while holding a handle: record server state and recovery.
Every test outcome is recorded, failures included. A failing test stays failing.

## Escalation triggers
Data corruption or server ABEND → capture the dump, mark the DASD as tainted, escalate to standard review and draft an upstream issue. Behavior that contradicts the OSE-005 audit → reopen the audit question.

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
Human direction: prioritize the reusable MVP development platform. This task remains BACKLOG until M0a acceptance recorded in OSE-014. Existing technical acceptance criteria and security requirements are unchanged; reuse the accepted platform when work starts.

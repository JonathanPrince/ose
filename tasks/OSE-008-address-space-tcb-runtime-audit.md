# OSE-008 — Address-space/TCB mechanisms and C runtime audit
Status: BACKLOG
Milestone: M0b (after reusable platform gate)
Dependencies: OSE-014 (M0a independently accepted with human gate approval); OSE-002, OSE-004 (needs the toolchain facts)
Owner:
Risk: high
Model tier: high
Reviewer tier: high
Budget: local-only
Branch: task/OSE-008-execution-model-audit
Guest resources: none for the audit. The experiments are designed here and run in M2.
Baseline commit:

## Goal and non-goals
Goal: list the mechanisms that **actually exist on MVS 3.8j** for creating and supervising units of work (ATTACH and subtasks, started tasks and address spaces via START/MGCR, ESTAE/ESTAI/STAE, WAIT/POST/ECB, ENQ, storage keys and subpools, any cross-memory facility). Assess how reentrant and isolatable the CC/370 and LIBC/370 runtime is. Turn each candidate into a runnable experiment design for M2 (spec §3.1).
Non-goals: implementation, privileged code, fork, any claim that a mechanism works before the experiment runs.

## Inputs and primary references
MVS 3.8j macro sources (SYS1.MACLIB and SYS1.AMODGEN on the pinned guest, or upstream copies) and historical IBM manuals for MVS 3.8, cited by form number. **Availability of cross-memory services (PC/PT and similar) on 3.8j is a hypothesis to verify, not an assumption.** libc370 source for global and static state, the atexit, stdio and heap implementations, and the ESTAE use. The OSE-004 toolchain note.

## Allowed files / interfaces
`docs/research/YYYY-MM-DD-execution-model-audit.md`, `docs/research/experiments/EXP-NNN-*.md` (design only: purpose, JCL/C sketch, measurements, pass/fail criteria, cleanup), this card.

## Acceptance tests (commands and expected outcomes)
The reviewer checks that:
1. Each mechanism lists the macro or source evidence at a pinned location, platform `MVS 3.8j`, and confidence. Any modern z/OS-only facility is explicitly excluded.
2. The runtime audit lists every piece of global mutable state in libc370 (with file:line) and how it behaves under ATTACH and when two programs share an address space.
3. There are at least two competing process models (for example a TCB per process within one address space, and an address space per process via START), each with isolation properties, storage-key behavior, cleanup on ABEND and disconnect, and identity propagation.
4. Experiment designs measure what spec §5 M2 requires: common and private storage, task creation time, concurrent capacity and resource recovery. Each design has explicit pass/fail criteria and runs only on disposable images.
5. Unknowns are listed together with the experiment that resolves each one.

## Escalation triggers
Conflicting sources about 3.8j behavior → record both and ask for human review. A design that needs a new SVC or authorized code → mark it as needing human approval (spec §3.2).

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

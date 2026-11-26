# OSE-011 — TSO terminal API and name-collision audit
Status: READY (source part; approved 2026-11-26; OSE-002 VERIFIED; guest listing still needs OSE-003)
Milestone: M0
Dependencies: OSE-002; OSE-003 for the guest listing
Owner:
Risk: low
Model tier: economy for extraction and listings; standard for the terminal API analysis
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-011-tso-terminal-audit
Guest resources: read-only listing job; lease required
Baseline commit:
Origin: added by the OSE-001 coordinator. It covers the spec §10 M0 question "terminal APIs" and the spec §3.5 "name subject to collision audit"; BOOTSTRAP.md had no card for either.

## Goal and non-goals
Goal: (a) list the terminal I/O facilities on MVS 3.8j TSO that an interactive shell could use, with evidence: TPUT/TGET, full-screen mode via STFSMODE/STLINENO/STTMPMD if present, and what existing full-screen programs on MVS/CE use. Also record what libc370 offers for terminal I/O. (b) Check that the proposed command name `OMVS`, the OSE data set high-level qualifier, the STC name and the SSI subsystem name do not collide with anything in the pinned image.
Non-goals: writing a terminal adapter.

## Inputs and primary references
MVS 3.8j TSO macros at the pin, historical TSO manuals by form number, libc370 source, the guest's CMDLIB/LINKLIB/LPALIB/PROCLIB member lists, and the subsystem names defined in IEFSSNxx.

## Allowed files / interfaces
`docs/research/YYYY-MM-DD-tso-terminal-audit.md`, `jcl/audit/list-libraries.jcl`, this card.

## Acceptance tests (commands and expected outcomes)
1. Each terminal facility has source evidence, platform `MVS 3.8j`, confidence, and notes on line mode versus full screen.
2. The listing job's RC is parsed. The collision table lists each candidate name with the libraries searched and the result.
3. A recommendation for the M1 terminal adapter approach, labeled a hypothesis.

## Escalation triggers
The only usable full-screen interface needs authorized code → flag for OSE-010 and the human.

## Handoff
- Changed files / commits:
- Commands run, RC, evidence paths:
- Tests not run and why:
- Decisions / ADRs:
- Known defects / blockers:
- Next action:
- Usage/cost if available:
## Independent review and gate result

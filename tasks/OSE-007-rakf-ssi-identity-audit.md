# OSE-007 — RAKF and SSI identity feasibility audit
Status: BACKLOG
Milestone: M0
Dependencies: OSE-002, OSE-005
Owner:
Risk: high (security boundary)
Model tier: high
Reviewer tier: high and human (security-critical; spec §3.4)
Budget: local-only
Branch: task/OSE-007-identity-audit
Guest resources: none for the audit. Optional read-only confirmation on a disposable image requires a lease.
Baseline commit:

## Goal and non-goals
Goal: build an evidence-based answer to whether a server address space on MVS 3.8j with RAKF can learn the identity of the user who sent a request (SSI, SVC or other path) in a way that client code cannot forge. Inventory every route by which a guest user can reach UFS data without going through OSE.
Non-goals: writing privileged code, SVCs or exits; changing RAKF profiles on a shared image; running negative tests (designing them is in scope).

## Inputs and primary references
- RAKF v2.0.0 source and docs at the pin, especially SVC 244 (recon R-04: the mvslovers servers "run authorized through RAKF's SVC 244 (no APF entries)").
- The OSE-005 identity findings.
- MVS 3.8j control blocks (ASCB, ASXB, TCB, ACEE as RAKF builds it, JSCB) taken from macros at the pin (SYS1.AMODGEN / MACLIB on the guest, or upstream source). **Not from z/OS documentation** (ADR-0002).
- Sysgen `profiles.conf` and `users.conf` at the pin (recon R-06: `DATASET * READ` hypothesis).
- FTPD, HTTPD and mvsMF source, for how each touches UFS and how each authenticates.

## Allowed files / interfaces
`docs/research/YYYY-MM-DD-identity-audit.md`, `docs/research/YYYY-MM-DD-threat-model-draft.md`, `tests/security/PLAN.md` (negative test plan; no executable code yet), this card.

## Acceptance tests (commands and expected outcomes)
The reviewer checks that:
1. Each candidate identity mechanism lists its source evidence, its confidence label, the trust assumption it rests on, and how an unprivileged program could subvert it.
2. SVC 244 is characterized: who may call it, what it grants, and whether it is a privilege-escalation path for ordinary users. Every claim cites a file and line.
3. The alternate access path inventory covers FTPD, HTTPD, mvsMF, libufs used directly, and direct data set access to UFS backing data sets under the default profiles. For each: the path, its current default state, how to restrict it, and the evidence.
4. A negative test plan for two ordinary users plus an admin (spec §6), with test IDs, preconditions and expected denials.
5. A threat model draft covering the spec §3.4 list, each threat mapped to a mitigation hypothesis or marked "open".
6. A clear feasibility verdict per mechanism: feasible / infeasible / unknown, with the experiment that would settle each "unknown".

## Escalation triggers
Evidence that default MVS/CE lets an ordinary user gain authorization or read other users' data → stop, write it up privately for the human, and do not publish details outside the repo. Any proposal for new authorized code goes to the human for decision.

## Handoff
- Changed files / commits:
- Commands run, RC, evidence paths:
- Tests not run and why:
- Decisions / ADRs:
- Known defects / blockers:
- Next action:
- Usage/cost if available:
## Independent review and gate result

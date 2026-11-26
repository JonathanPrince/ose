# Project status

Updated: 2026-11-26 by the coordinator (OSE-002 VERIFIED and merged)
Milestone: **M0, Reproducible baseline and source audit**: in progress
Guest lease: none held. No guest image exists yet. See tasks/README.md "Guest resources".

## Summary
Bootstrap (OSE-001) and the first inventory (OSE-002) are done. ADRs 0001–0005 are accepted; 0003 chose option A, a pinned Debian container. OSE-002 went through two review rounds and is **VERIFIED** (2026-11-26) under the gate the human amended: OSE-002 records the pins, and OSE-013 enforces them, with the end-to-end proof in OSE-003 test 7. OSE-011, 012 and 013 are approved, and wave 1 is READY. **No build, guest or test has run yet**, apart from host-side repository checks. Nothing in `src/` exists.

## M0 gate (spec §5) → owning tasks

| Gate criterion | Tasks | Evidence | State |
|---|---|---|---|
| Clean pinned Sysgen build boots twice | 002, 013, 003 | | not started (pins recorded, enforcement pending) |
| Native TSO/JES smoke tests | 003 | | not started |
| Compile/deploy hello | 004 | | not started |
| UFSD read/write across two guest clients | 005, 006 | | not started |
| Dependency/license inventory | 002 | dependencies.lock.json (38 components, 2 excluded, 2 pending_enforcement owned by OSE-013); research 2026-11-26-sysgen-pins, -licensing | VERIFIED 2026-11-26 (pin enforcement pending: OSE-013, OSE-003 test 7) |
| Actual interfaces documented | 005, 007, 008, 011, 012 | | not started |
| Recovery documented | 009 | | not started |
| Spec §10 questions answered (versions, build host, terminal APIs, C subset, RAKF baseline, macros, UFSD identity) | 002, 003, 011, 012, 007, 008, 005 | versions and RAKF baseline recorded (OSE-002); build host chosen (ADR-0003) | partial |

## Task board

| Task | Title | Status | Tier | Owner |
|---|---|---|---|---|
| OSE-001 | Repository bootstrap | REVIEW | (coordinator) | coordinator |
| OSE-002 | Upstream inventory and pins (records pins; gate amended) | VERIFIED (merged to main) | economy, standard review | coordinator |
| OSE-003 | Build host doctor and sysgen | BACKLOG (ADR-0003 accepted; needs OSE-013) | standard | — |
| OSE-004 | CC/370 + MBT hello | REVIEW (host accepted; guest acceptance 2-4 pending) | standard | — |
| OSE-005 | UFSD interface audit | READY | standard → high | — |
| OSE-006 | UFSD cross-space tests | BACKLOG | standard | — |
| OSE-007 | RAKF/SSI identity audit | BACKLOG | high | — |
| OSE-008 | Execution model and runtime audit | BACKLOG | high | — |
| OSE-009 | Guest lease, snapshot, recovery | BACKLOG | standard | — |
| OSE-010 | M0 gate review | BACKLOG | high and human | — |
| OSE-011 | TSO terminal and name audit | READY (source part) | economy → standard | — |
| OSE-012 | C subset and libc POSIX inventory | READY | economy, standard review | — |
| OSE-013 | Enforce MVP and RAKF pins | READY | standard | — |

## Decisions needed from the human
Resolved 2026-11-26 (OSE-004): maclib370 v1.0.0 `e85286a7` approved into the lock (option a). Open from it: macro licensing (licensing question 10), and showing on a guest that the TK5-derived macros work on MVS/CE.

Resolved 2026-11-26: the OSE-002 gate was amended (recording only; enforcement in OSE-013), and OSE-011, 012 and 013 were approved.

1. **Spec amendments to consider** (staleness, not contradictions):
   - §2 RAKF row: `MVS-sysgen/RAKF` redirects to `mvslovers/RAKF`, so there are no two variants to compare. Sysgen installs v2.1.0.
   - §3.3 lists `/home`, but pinned Sysgen provides `/u/<user>` home file systems (recon R-03).
   - §2 has no rows for SDL Hercules, hercules-helper or the MVP packages. All are M0 dependencies.
2. **Licensing questions 1–9** in `docs/research/2026-11-26-licensing.md`. The 22 MVP packages that sysgen installs have no explicit redistribution grant. These questions block redistribution only, not local M0 work.
3. **ADR "Deciders" lines** in 0001, 0002, 0004 and 0005 still say "(pending)" although their Status is Accepted. Only the human should edit them.

## Risks (hypotheses until audited)
- The mvslovers servers run authorized via RAKF SVC 244 (recon R-04). Who else can obtain authorization this way is unknown. Owner: OSE-007.
- The default RAKF profile `DATASET * READ` may let any user read UFS backing data sets directly (recon R-06). Owner: OSE-007.
- FTPD, HTTPD and mvsMF are installed (not started) and are alternate paths to UFS data. Owner: OSE-007.
- MVP package jobstreams carry `USER=IBMUSER,PASSWORD=SYS1`. Whether the default stays usable after sysgen is unchecked (sysgen-pins P-8). Owner: OSE-007.
- **Windows `core.autocrlf=true` silently corrupts MVP text packages** in a working tree (sysgen-pins P-9). Caches must be cloned with `core.autocrlf=false` and hash-verified. Owners: OSE-003, OSE-013.
- Upstream is very active. Pins must follow Sysgen (ADR-0004), and MVP pinning is not enforced yet (OSE-013).

## Next actions
1. Human: decisions 1–3 above.
2. Critical path: OSE-013 (host-verified pin enforcement), then OSE-003 (container build host, sysgen, and the end-to-end pin proof in test 7).
3. In parallel, on disjoint files: OSE-005 (UFSD audit at v1.5.2), OSE-012 inventory (libc370 v2.25.1 = fcde4e88), OSE-011 source part, OSE-004 host part. The leads in research sysgen-pins P-6 and P-8 are context for 004, 005 and 007.

## Independent review — 2026-11-26

OSE-004: changes requested for container Git discovery in worktrees (R04-1). Exported-tree rebuild succeeds and reproduces all four recorded hashes. Guest deployment/execution acceptance stays open. See task card for commands and evidence.

## OSE-004 independent re-review — 2026-11-26

Host portion accepted at 0d13ac2: R04-1 closed by independent complete worktree build (RC 0), all five artifact hashes match and 11 host tests pass. Task remains REVIEW until guest acceptance 2-4. See the task card for evidence; human owns integration.

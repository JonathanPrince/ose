# Project status

Updated: 2026-11-26 by OSE-001 (bootstrap coordinator)
Milestone: **M0, Reproducible baseline and source audit**: in progress
Guest lease: none held. No guest image exists yet. See tasks/README.md "Guest resources".

## Summary
The repository structure, conventions, task cards and proposed process ADRs are in place. A read-only upstream reconnaissance has been recorded. **No build, guest or test has run yet.** Nothing in `src/` exists.

## M0 gate (spec §5) → owning tasks

| Gate criterion | Tasks | Evidence | State |
|---|---|---|---|
| Clean pinned Sysgen build boots twice | 002, 003 | | not started |
| Native TSO/JES smoke tests | 003 | | not started |
| Compile/deploy hello | 004 | | not started |
| UFSD read/write across two guest clients | 005, 006 | | not started |
| Dependency/license inventory | 002 | dependencies.lock.json; research 2026-11-26-sysgen-pins, -licensing | implemented, awaiting review |
| Actual interfaces documented | 005, 007, 008, 011, 012 | | not started |
| Recovery documented | 009 | | not started |
| Spec §10 questions answered (versions, build host, terminal APIs, C subset, RAKF baseline, macros, UFSD identity) | 002, 003, 011, 012, 007, 008, 005 | | not started |

## Task board

| Task | Title | Status | Tier | Owner |
|---|---|---|---|---|
| OSE-001 | Repository bootstrap | REVIEW | (coordinator) | coordinator |
| OSE-002 | Upstream inventory and pins | IMPLEMENTED (needs review) | economy, standard review | coordinator |
| OSE-003 | Build host doctor and sysgen | BACKLOG (blocked by ADR-0003 decision) | standard | — |
| OSE-004 | CC/370 + MBT hello | BACKLOG | standard | — |
| OSE-005 | UFSD interface audit | BACKLOG | standard → high | — |
| OSE-006 | UFSD cross-space tests | BACKLOG | standard | — |
| OSE-007 | RAKF/SSI identity audit | BACKLOG | high | — |
| OSE-008 | Execution model and runtime audit | BACKLOG | high | — |
| OSE-009 | Guest lease, snapshot, recovery | BACKLOG | standard | — |
| OSE-010 | M0 gate review | BACKLOG | high and human | — |
| OSE-011 | TSO terminal and name audit (new) | BACKLOG | economy → standard | — |
| OSE-012 | C subset and libc POSIX inventory (new) | BACKLOG | economy, standard review | — |

## Decisions needed from the human
1. **Build host (ADR-0003):** option A (pinned Debian container, proposed) or B (Ubuntu WSL). This blocks OSE-003.
2. **Accept or amend ADRs 0001, 0002, 0004 and the new 0005** (toolchain = UFSD 1.5.2 build: cc370 1.6.3 / libc370 2.25.1 / mbt 3.0.1; Hercules 4.9.1; MVP pin via sysgen patch P-01). Note: an agent cannot mark ADRs Accepted; the human edits the Status line.
3. **Approve the new cards OSE-011 and OSE-012** and the clarified dependencies in `tasks/BOOTSTRAP.md`.
4. **Spec amendments to consider** (spec §8 says contradictions block work. These are only staleness, so they block nothing yet):
   - §2 RAKF row: `MVS-sysgen/RAKF` now redirects to `mvslovers/RAKF`, so there are no two variants to compare. Sysgen installs v2.1.0 (recon R-02 as corrected).
   - §3.3 lists `/home`, but pinned Sysgen already provides `/u/<user>` home file systems (recon R-03).
   - §2 has no row for the emulator (SDL Hercules) or for hercules-helper. Both are M0 dependencies.
5. **Licensing questions 1–5** in `docs/research/2026-11-26-licensing.md`. RAKF's license is restrictive, and sysgen, MVP, sdsf and mbt have no license file. These block redistribution only, not local M0 work.
6. **Initial commit:** the working tree has not been committed. The human makes the first commit (AGENTS.md: the human owns merges).

## Risks noted during bootstrap (hypotheses until audited)
- The mvslovers servers run authorized via RAKF SVC 244 (recon R-04). Who else can obtain authorization this way is unknown. Owner: OSE-007.
- The default RAKF profile `DATASET * READ` may let any user read UFS backing data sets directly (recon R-06). Owner: OSE-007.
- FTPD, HTTPD and mvsMF are installed (not started) and are alternate paths to UFS data. Spec §3.3 requires restricting them before any security claim. Owner: OSE-007.
- Upstream is very active (most repositories were pushed in Nov 2026). Pins must follow Sysgen (ADR-0004).
- The workstation has no supported build OS (recon R-07).

## Next actions
1. Human: decisions 1–6 above. ADR-0003 is the most urgent because it unblocks OSE-003.
2. OSE-002 review by an independent standard-tier agent or a human.
3. Wave 1 can start now from the pins: OSE-005 (UFSD audit at v1.5.2 = 1a63bf52), OSE-012 inventory (libc370 v2.25.1 = fcde4e88), OSE-011 source part, OSE-004 host part. OSE-003 once ADR-0003 is accepted. The leads in research sysgen-pins P-6 are context for 005, 007 and 004.

# Project status

Updated: 2026-11-26 by the coordinator (OSE-004, 005, 011, 012 and 013 merged to main on the human maintainer's instruction)
Milestone: **M0, Reproducible baseline and source audit**: in progress
Guest lease: **held by OSE-003** (coordinator session; DASD set `ose-sysgen-1`, a Docker volume created by `scripts/sysgen.sh` and exported to `artifacts/sysgen/`; since 2026-11-26T21:17Z). Release on OSE-003 handoff. See tasks/README.md "Guest resources".

## Summary
Bootstrap (OSE-001) and the first inventory (OSE-002) are done. ADRs 0001–0005 are accepted; 0003 chose option A, a pinned Debian container.

Merged to main after independent review (2026-11-26):
- **OSE-013:** pin enforcement, host-verified.
- **OSE-005:** UFSD source audit.
- **OSE-012:** libc370 inventory and compile probes.
- **OSE-011:** terminal audit, source part. The guest listing is still open.
- **OSE-004:** CC/370 toolchain and a reproducible hello load module, host part. Guest acceptance tests 2–4 are still open.

**No guest exists yet.** Everything observed so far is host-side: repository checks, the pin tests, and the CC/370 compile and link inside the container. `src/` holds only the OSE-004 test program `src/utils/hello/hello.c`.

## M0 gate (spec §5) → owning tasks

| Gate criterion | Tasks | Evidence | State |
|---|---|---|---|
| Clean pinned Sysgen build boots twice | 002, 013, 003 | `upstream/sysgen/MANIFEST.md` (P-01 patch, validate-before-consumption interface); T-PIN-001..009 | not started (enforcement host-verified; OSE-003 owns the run and test 7) |
| Native TSO/JES smoke tests | 003 | | not started |
| Compile/deploy hello | 004 | `make build` RC 0; HELLO load module and XMIT reproducible (research 2026-11-26-toolchain T-7; runbook hello-compile-deploy) | host part accepted and merged; deploy and guest runs not started |
| UFSD read/write across two guest clients | 005, 006 | research 2026-11-26-ufsd-audit (source only) | source audit VERIFIED; guest tests not started |
| Dependency/license inventory | 002, 004 | dependencies.lock.json (39 components incl. maclib370, 2 excluded, 2 pending_enforcement now host-verified by OSE-013); research 2026-11-26-sysgen-pins, -licensing | VERIFIED 2026-11-26 (end-to-end pin proof: OSE-003 test 7) |
| Actual interfaces documented | 005, 007, 008, 011, 012 | docs/interfaces/ufsd-observed.md; research -ufsd-audit, -libc370-inventory, -tso-terminal-audit | partial (005, 011 source part, 012 done; 007, 008 not started) |
| Recovery documented | 009 | | not started |
| Spec §10 questions answered (versions, build host, terminal APIs, C subset, RAKF baseline, macros, UFSD identity) | 002, 003, 011, 012, 007, 008, 005 | versions and RAKF baseline (OSE-002); build host (ADR-0003); terminal APIs (OSE-011); C subset (OSE-012); UFSD identity: client-asserted, not verified (OSE-005 U-3) | partial (RAKF and SSI identity: OSE-007) |

## Task board

| Task | Title | Status | Tier | Owner |
|---|---|---|---|---|
| OSE-001 | Repository bootstrap | REVIEW | (coordinator) | coordinator |
| OSE-002 | Upstream inventory and pins (records pins; gate amended) | MERGED (VERIFIED) | economy, standard review | coordinator |
| OSE-003 | Build host doctor and sysgen | READY (OSE-013 VERIFIED and merged; follow MANIFEST steps 2–3b incl. `--keep-temp`) | standard | — |
| OSE-004 | CC/370 + MBT hello | REVIEW, host part MERGED (accepted); guest acceptance 2-4 pending OSE-003 | standard | — |
| OSE-005 | UFSD interface audit | MERGED (VERIFIED, source-audit scope; runtime gaps tracked) | standard → high | — |
| OSE-006 | UFSD cross-space tests | BACKLOG (needs OSE-003; inherits OSE-005 hypotheses incl. G-6, G-15) | standard | — |
| OSE-007 | RAKF/SSI identity audit | BACKLOG (OSE-005 escalations G-1, G-2, G-11, G-12 waiting) | high | — |
| OSE-008 | Execution model and runtime audit | BACKLOG | high | — |
| OSE-009 | Guest lease, snapshot, recovery | BACKLOG | standard | — |
| OSE-010 | M0 gate review | BACKLOG | high and human | — |
| OSE-011 | TSO terminal and name audit | REVIEW, source part MERGED (accepted); guest listing pending OSE-003 | economy → standard | — |
| OSE-012 | C subset and libc POSIX inventory | MERGED (VERIFIED, static inventory and compile probes) | economy, standard review | — |
| OSE-013 | Enforce MVP and RAKF pins | MERGED (VERIFIED, host enforcement; OSE-003 test 7 pending) | standard | — |

## Decisions needed from the human
Resolved 2026-11-26:
- The OSE-002 gate was amended (recording only; enforcement in OSE-013).
- OSE-011, 012 and 013 were approved.
- maclib370 was approved for the lock (OSE-004, option a).
- OSE-004 (host part), 005, 011 (source part), 012 and 013 were merged on the human's instruction.

1. **Spec amendments to consider** (staleness, not contradictions):
   - §2 RAKF row: `MVS-sysgen/RAKF` redirects to `mvslovers/RAKF`, so there are no two variants to compare. Sysgen installs v2.1.0.
   - §3.3 lists `/home`, but pinned Sysgen provides `/u/<user>` home file systems (recon R-03).
   - §2 has no rows for SDL Hercules, hercules-helper or the MVP packages. All are M0 dependencies.
2. **Licensing questions 1–10** in `docs/research/2026-11-26-licensing.md`. Question 10 asks whether OSE may redistribute build outputs containing maclib370's IBM macro expansions, or maclib370 itself. These questions block redistribution only, not local M0 work.
3. **ADR "Deciders" lines** in 0001, 0002, 0004 and 0005 still say "(pending)" although their Status is Accepted. Only the human should edit them.
4. **Candidate OSE names** (OSE-011 N-1): TSO command `OMVS` or `OSH`, HLQ `OSE`, STC `OSE` or `OSED`, subsystem `OSE1` or `OSES`. The subsystem name must differ from the STC name. Confirm after the guest listing.
5. **Upstream reports** (OSE-005): UFSD unmount with open handles (U-7.5), orphaned requests after a client cancel (U-5.7), block double allocation after an I/O failure (U-7.6a), and the concept.md vs code mismatch on ACEE capture (U-3.5). Outreach needs your approval.

## Risks (hypotheses until tested on a guest)
- **UFSD identity is client-asserted** (`SESS_OPEN`/`SETUSER`, never verified), every client must be APF-authorized, and sessions are not bound to an ASID (OSE-005 U-1, U-3, U-5). A trusted broker is required. Owner: OSE-007, then OSE-010.
- UFSD integrity: an unmount with open handles redirects them to another file system (G-6), and an I/O failure in truncate or unlink can double-allocate blocks (G-15). Both are rated M1. Owner: OSE-006.
- The mvslovers servers run authorized via RAKF SVC 244 (recon R-04). Who else can obtain authorization this way is unknown. Owner: OSE-007.
- The default RAKF profile `DATASET * READ` may let any user read UFS backing data sets directly (recon R-06). Owner: OSE-007.
- FTPD, HTTPD and mvsMF are installed (not started) and are alternate paths to UFS data. `mbt deploy` itself uses mvsMF over HTTP Basic (OSE-004 T-6). Owner: OSE-007.
- MVP package jobstreams carry `USER=IBMUSER,PASSWORD=SYS1`. Whether the default stays usable after sysgen is unchecked (sysgen-pins P-8). Owner: OSE-007.
- **Windows `core.autocrlf=true` silently corrupts MVP text packages** in a working tree (sysgen-pins P-9). Clones must use `core.autocrlf=false` and be validated before use (MANIFEST steps 2–3). Owner: OSE-003.
- The toolchain macros (maclib370) come from TK5, not MVS/CE. Whether libc370 built against them runs correctly on MVS/CE needs a guest run (OSE-004 T-1).

## Next actions
1. **Critical path: OSE-003.** Container build host, a pinned sysgen run following `upstream/sysgen/MANIFEST.md` steps 1–3b (including `--keep-temp`), IPL twice, and test 7, which removes the `pending_enforcement` entries. It needs a guest lease (OSE-009 defines the procedure).
2. After OSE-003: the OSE-011 guest listing, the OSE-004 guest acceptance tests 2–4, and the OSE-006 UFSD guest tests.
3. In parallel, at high tier: OSE-007, starting from the OSE-005 escalations, and OSE-008.

## Review log
Entries written by the independent reviewer, kept verbatim. The round-2 OSE-013 entry ("not VERIFIED; awaiting check") was superseded by the round-3 entry below.

OSE-013: VERIFIED (host-enforcement scope; independent re-review 2026-11-26). See the task card for tested scope and evidence.
OSE-005: VERIFIED (source-audit scope; independent re-review 2026-11-26). See the task card for tested scope and evidence.
OSE-012 VERIFIED: header/probe findings resolved, ten-entry source sample checked, and all eleven expected compile/assemble outcomes independently reproduced. Guest runtime behavior remains outside this task.
OSE-011: REVIEW (source part accepted; guest collision listing remains open). See the task card for tested scope and evidence.

## OSE-004 independent re-review — 2026-11-26

Host portion accepted at 0d13ac2: R04-1 closed by independent complete worktree build (RC 0), all five artifact hashes match and 11 host tests pass. Task remains REVIEW until guest acceptance 2-4. See the task card for evidence; human owns integration.

# Project status

Updated: 2026-11-27, platform-first specification amendment at the human request (implementation gates still open)
Milestone: **M0a, reusable MVP development platform**: in progress; M0b OSE audits follow its acceptance
Guest lease: use `make lease-status` / scripts/guest/guest.py (OSE-009 VERIFIED; protocol activated through human integration). No review leases held; reviewer volumes ose-review-009-r2-a and ose-review-009-r2-b retained stopped.

## Summary
Bootstrap (OSE-001) and the first inventory (OSE-002) are done. ADRs 0001–0005 are accepted; 0003 chose option A, a pinned Debian container.

Merged to main after independent review (2026-11-26):
- **OSE-013:** pin enforcement, host-verified.
- **OSE-005:** UFSD source audit.
- **OSE-012:** libc370 inventory and compile probes.
- **OSE-011:** terminal audit (source part) and the guest name-collision listing: no collision for the candidate names on the pinned image (research tso-terminal-audit N-4).
- **OSE-004:** reproducible host build, guest deploy/listing, batch RC/output and TSO invocation accepted and merged.

**The generic build/deploy baseline is accepted.** OSE-003/004 findings are closed in merged work. Next: OSE-009 isolation/recovery, then OSE-014 generic packaging/export and M0a acceptance. `src/` holds only the OSE-004 test program `src/utils/hello/hello.c`.

## M0a platform gate → owning tasks

| Gate criterion | Tasks | Evidence/state |
|---|---|---|
| Pinned host/guest builds; repeated IPL/JES/TSO; reproducible HELLO deploy and runtime | 002, 003, 004, 012, 013 | accepted baseline evidence retained; independent clean-checkout platform repeat still required by 014 |
| Generic leases, isolated ports/volumes, snapshot/restore and corruption rejection | 009 | met: 6f13967 VERIFIED; all six findings closed; independent 15-check recovery repeat passes |
| Package configuration and shared harness; real MVP package install/runtime/recovery | 014 | BACKLOG, waits for 009; XMIT RECEIVE alone is insufficient |
| Second independent example through unchanged shared harness | 014 | not run |
| Standalone export, dependency rights/provenance, version and OSE consumption plan | 014 | not run; no publication authorization implied |
| Independent review and human M0a acceptance | 014 | pending; required before new OSE-specific work |

## M0b OSE gate → owning tasks (after M0a)

| Gate criterion | Tasks | Evidence/state |
|---|---|---|
| UFSD read/write across two guest clients, persistence and failures | 005, 006 | source audit accepted; 006 waits for M0a |
| Trusted identity, alternate access paths and OSE security feasibility | 005, 007 | known gaps retained; 007 waits for M0a |
| Execution mechanisms/runtime feasibility and actual OSE interfaces | 008, 011, 012 | 011/012 accepted evidence; 008 waits for M0a |
| Remaining M0 questions, UFSD/toolchain/process decisions and M1 decomposition | 010 | requires M0a and OSE audits; no security requirement waived |

## Task board

| Task | Title | Status | Tier | Owner |
|---|---|---|---|---|
| OSE-001 | Repository bootstrap | REVIEW | (coordinator) | coordinator |
| OSE-002 | Upstream inventory and pins (records pins; gate amended) | MERGED (VERIFIED) | economy, standard review | coordinator |
| OSE-003 | Build host doctor and sysgen | MERGED (VERIFIED at 85414c2; ADR-0006 accepted) | standard | coordinator |
| OSE-004 | CC/370 + MBT hello | MERGED (VERIFIED; host and guest parts) | standard | coordinator |
| OSE-005 | UFSD interface audit | MERGED (VERIFIED, source-audit scope; runtime gaps tracked) | standard → high | — |
| OSE-006 | UFSD cross-space tests | BACKLOG (M0b; waits for M0a/014) | standard | — |
| OSE-007 | RAKF/SSI identity audit | BACKLOG (M0b; waits for M0a/014; existing escalations retained) | high | — |
| OSE-008 | Execution model and runtime audit | BACKLOG (M0b; waits for M0a/014) | high | — |
| OSE-009 | Generic guest lease, snapshot, recovery | VERIFIED (6f13967; R09-1..R09-6 closed; human integration pending) | high re-review | coordinator |
| OSE-010 | M0b OSE gate review | BACKLOG (after M0a and OSE audits) | high and human | — |
| OSE-011 | TSO terminal and name audit | MERGED (VERIFIED; source part and guest listing: no name collision) | economy → standard | coordinator |
| OSE-012 | C subset and libc POSIX inventory | MERGED (VERIFIED, static inventory and compile probes) | economy, standard review | — |
| OSE-013 | Enforce MVP and RAKF pins | MERGED (VERIFIED; end-to-end OSE-003 test 7 passed and merged) | standard | — |
| OSE-014 | Reusable MVP platform and M0a export gate | BACKLOG (after 009; before OSE-specific work) | standard + independent/human gate | — |

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
1. Integrate VERIFIED OSE-009 (6f13967 and independent review), including the reviewed lease protocol; then prepare OSE-014 for claim.
2. Complete OSE-014: separate package configuration from shared tooling, implement actual MVP packaging/install tests and a second example, validate the standalone export, then obtain independent review and human M0a acceptance.
3. After M0a, start OSE-006/007/008 using that platform, then OSE-010 for the remaining M0b/OSE gate and M1 queue. Existing security requirements remain mandatory. Repository publication remains a separate human decision.

## Review log
Entries written by the independent reviewer, kept verbatim. The round-2 OSE-013 entry ("not VERIFIED; awaiting check") was superseded by the round-3 entry below.

OSE-013: VERIFIED (host-enforcement scope; independent re-review 2026-11-26). See the task card for tested scope and evidence.
OSE-005: VERIFIED (source-audit scope; independent re-review 2026-11-26). See the task card for tested scope and evidence.
OSE-012 VERIFIED: header/probe findings resolved, ten-entry source sample checked, and all eleven expected compile/assemble outcomes independently reproduced. Guest runtime behavior remains outside this task.
OSE-011: REVIEW (source part accepted; guest collision listing remains open). See the task card for tested scope and evidence.

## OSE-004 independent re-review — 2026-11-26

Host portion accepted at 0d13ac2: R04-1 closed by independent complete worktree build (RC 0), all five artifact hashes match and 11 host tests pass. Task remains REVIEW until guest acceptance 2-4. See the task card for evidence; human owns integration.

## OSE-003 independent review — 2026-11-27

Test 6 completed: fresh worktree/new volume; fetch/doctor/build/smoke RC 0; Hercules 293/293; Sysgen attempt 1 in 3181 s; cold IPLs 7 and 9 s; raw JES2 RCs 0000/0004; non-admin TIME/logoff; both shutdowns clean. Changes requested R03-1..R03-5 (resume source pin, doctor status, shutdown evidence, stale smoke handshake, s3270 pin). See task card and ignored review evidence. Lease released after containers exited; no author volume changed.

## OSE-003 re-review — 2026-11-27

Reviewed b5cbb7d: 44 host tests (35 pass, 9 skipped), healthy real-tree read-only admission and pins pass, doctor passes, two consecutive guest smoke cycles pass (four IPLs 9/9/8/9 s, JES2 0000/0004 and TSO twice, clean ordered shutdowns). Two additional missing/invalid expected-patch cases expose the remaining fail-open verifier (R03-1 P1): failed git apply is ignored and an unpatched tree is admitted. R03-2..5 technical fixes accepted. ADR-0006 is still proposed. Changes requested; lease released, author volumes untouched. See task card and review/OSE-003-r2 evidence.

## OSE-003 focused re-review — 2026-11-27

85414c2 VERIFIED: R03-1 fail-open path closed, independent missing/invalid patch cases now return 10, host suite 41 passed/9 skipped, and no new findings. R03-2..5 and runtime evidence remain accepted from prior reviews; ADR-0006 is recorded accepted by the human. No new guest run or lease. Human owns integration.

## Reusable development environment direction — 2026-11-27 (historical; superseded by platform-first amendment below)

The human requested a separate repository that reuses the M0 development foundation for other MVS/CE MVP package projects. Spec §§1.1/4.1/5.1 now define the boundary and export gate; OSE-014 is BACKLOG after the existing M0 gate, independent of M1–M5. Export acceptance requires clean independent reproduction, a real MVP package installation, a second example using shared harness code, recovery/evidence checks, license/provenance review and a versioned OSE consumption plan. Extraction and publication have not started; repository destination and release remain human decisions. Existing M0 security gates remain in force.

## OSE-004 independent guest review — 2026-11-27

Reviewed 9a57b02 on `review/OSE-004-guest-r1`: changes requested R04G-1 (RECV/CLEANUP execute when GONE bypasses STAGE, reproduced on MVS 3.8j) and R04G-2 (failed evidence export returns success, mocked reproduction). Independent deploy/list, batch 0000/0004 with exact output, TSO CALL7 and clean shutdowns passed. Host suite RC0: 54 passed, 9 skipped; repo check RC0. Author OSE-004 manifest 64/64 verified; OSE-003 exactly the 9 disclosed damaged entries, originals not repaired. See OSE-004 card for commands/evidence and rework. Lease released; no running review containers; disposable reviewer volume `ose-review-004-20261127` retained stopped. No merge/push.

## OSE-004 guest re-review — 2026-11-27

`c76f088` VERIFIED on `review/OSE-004-guest-r2`, high-tier independent re-review: R04G-1/R04G-2 (author R04-2/R04-3) closed, no new findings. Real stale-library test skips STAGE/RECV/CLEANUP with no second RECEIVE; normal deploy/list, batch 0000/0004 with exact output, TSO CALL7 and smoke IPL pass. Four clean IPL/shutdown cycles; verified exports. Host suite RC0: 59 passed/9 skipped (source caches absent); extra evidence failure mocks fail correctly and retain guest copies. Author's 26 rework hashes and previous review's 32 hashes unchanged. See card for exact commands/evidence and limits. Lease released; all containers stopped; disposable reviewer volume `ose-review-004-r2-20261127` retained stopped. Human merge pending.

## OSE-011 independent guest review — 2026-11-27

Reviewed 6880303 on `review/OSE-011-guest-r1`: positive guest acceptance independently reproduced (32 libraries, 3825 distinct names, no candidate collision; live configuration coverage, catalog and static subsystem table checked). One P2 finding R11G-1: unparsed member lines or missing subsystem dump still yield driver RC0/ok=true; deterministic altered-spool replays retained. Changes requested, source portion remains accepted. Host suite RC0: 69 passed/9 skipped; repo check RC0; author manifest 20/20 verified. See card for exact commands and limits. Lease released; all containers stopped; reviewer volume `ose-review-011-20261127` retained stopped. No merge or push.

## OSE-011 focused re-review — 2026-11-27

665604f closes R11G-1: independent intact guest-spool replay passes; four damaged evidence variants fail correctly. New P2 R11G-2: MainReplay's whole-environment clear/restore removes an inherited empty Git config variable from native Windows inheritance; clean git init RC0 before replay tests, RC128 after. Full host suite: 69 passed, 11 errors, 9 skipped (RC1). Changes requested, not VERIFIED. Author rework hashes 5/5 verified. No new guest run/lease or implementation changes; prior independent guest listing remains valid. See card/evidence on `review/OSE-011-guest-r2`. No merge/push.

## OSE-011 final focused re-review — 2026-11-27

5815701 VERIFIED on `review/OSE-011-guest-r3`: R11G-2 closed, no new findings. Full Windows host suite RC0: 81 passed/9 skipped, including all previously failing Git admission fixtures; independent native git-init probe RC0 before and after replay tests. Prior independent guest listing and R11G-1 closure remain accepted, evidence unchanged (25/25 prior reviewer hashes verified). No new guest work/lease, dependency change, merge or push. See task card for exact commands/evidence and scope. Human integration pending.

## Platform-first sequencing amendment — 2026-11-27

The human requested the generic MVP development platform before further OSE-specific tasks. This supersedes the earlier “OSE-014 after OSE-010” planning entry above: OSE-009 → OSE-014/M0a → OSE-006/007/008 → OSE-010/M0b → M1. Completed audits and review records remain evidence. Only documentation/task sequencing changed; no new gate acceptance, guest run, export or publication is claimed.

## OSE-009 independent review — 2026-11-27

Reviewed dc83bd5 on `review/OSE-009-r1`: changes requested R09-1..R09-6 (negative-pin target/source lease handling; restore rollback after users.conf failure; Docker busy-query failure admitted as stopped; exit cleanup releases a still-running guest; restore --create mutates before lease validation; whole-environment test patch breaks Git fixtures on Windows). Independent end-to-end recovery RC0/zero failures, including concurrent guests/ports, SIGKILL marker survival, restore/marker absence, JES/TSO and corruption refusal. Full host suite RC1: 89 passed, 11 errors, 9 skipped; author hashes31/31 match. Detailed reproduced fault evidence in OSE-009 card. Actual containers stopped and tool/manual review leases released; own reviewer volumes retained stopped. Keep manual lease protocol; no OSE-014 start, merge or push.

## OSE-009 independent re-review — 2026-11-27

6f13967 VERIFIED on `review/OSE-009-r2`: all six findings closed, no new findings. Full Windows host suite RC0 (117 passed/9 skipped), prior independent fault reproductions now pass, pinned-image restore cases return expected 0/7/7/8, and full real recovery repeat RC0 with all 15 checks passing. Live container labels matched own lease tokens. Author rework/recovery and prior reviewer manifests all match. No running containers or actual tool leases; manual review lease released; own reviewer guests retained stopped. Reviewed tool protocol replaces the manual ledger through human integration; tasks/README.md updated accordingly. OSE-014 next, M0a still open. No merge or push.

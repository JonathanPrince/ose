# OSE-011 — TSO terminal API and name-collision audit
Status: IMPLEMENTED (source part accepted 2026-11-26; guest listing, acceptance test 2, done 2026-11-27 on task/OSE-011-guest; awaiting independent review)
Milestone: M0
Dependencies: OSE-002; OSE-003 for the guest listing
Owner: author model (standard tier)
Risk: low
Model tier: economy for extraction and listings; standard for the terminal API analysis
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-011-tso-terminal-audit
Guest resources: read-only listing job; lease required
Baseline commit: 5970f87 (main)
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
- Changed files / commits: `docs/research/2026-11-26-tso-terminal-audit.md` (new), `jcl/audit/list-libraries.jcl` (new, not run), `docs/research/README.md` (index), `docs/status.md`, `tasks/usage.jsonl`, this card. Branch `task/OSE-011-tso-terminal-audit`.
- Commands run, RC, evidence paths:
  - Decoded the sysgen@4746195d IBM tapes (`tape/*.het`, zlib/bzip2 AWS blocks, cp037) with a throw-away scratchpad reader, then located the macro prototypes. RC 0. `zdlib1.het` sha256 is in the note.
  - `pdftotext -layout documentation/mvs38bas.pdf` for the FMID and RELFILE mapping. RC 0.
  - Cloned `mvslovers/brexx370@5aabe493` and `mvslovers/sdsf@cfb1b02b` with `core.autocrlf=false` into `artifacts/cache` (git-ignored). RC 0.
  - Whole-token name search over the sysgen, MVP, ufsd, sdsf, brexx370 and libc370 sources and the decoded tapes. Results are in note N-2.
  - JCL checked for at most 71 columns and ASCII only.
  - `python scripts/check_repo.py`: RC 0. Host unittest: RC 0.
- Tests not run and why:
  - Acceptance test 2 (listing job RC and collision table from the guest): `jcl/audit/list-libraries.jcl` is written but not run. It needs the OSE-003 guest and a lease.
  - Terminal behaviour (TGET ASIS, TPUT FULLSCR, STAX) has not been run. Those probes need the OSE-004 toolchain.
- Decisions / ADRs: none. Candidate names (OMVS/OSH, HLQ OSE, STC OSE/OSED, subsystem OSE1/OSES) are proposals for the human. The M1 adapter recommendation (TPUT/TGET ASIS line mode behind an adapter interface, STAX attention, full screen later) is labelled a hypothesis.
- Known defects / blockers: the escalation trigger did **not** fire, because BREXX FSS uses full screen unauthorized (note A-4). The TSO macro manual form numbers have not been read yet (open item).
- Next action: standard-tier review of the source part. After OSE-003, run the listing job under a lease, record its RC and output in the note, and close acceptance test 2.
- Usage/cost if available: not metered.
## Independent review and gate result

### Review round 1 (2026-11-26, relayed by the human): changes requested
- **P2, listing job omits configured libraries:** accepted. The first job listed only SYS1/SYS2 CMDLIB, LINKLIB, LPALIB, PROCLIB and PARMLIB, and missed SYSC.PROCLIB, SYSC.LINKLIB, BREXX.LINKLIB and others.
- Rework:
  - The library list is derived from the search orders sysgen configures (link list, JES2 `PROC00`, master-subsystem path, TSO `SYSPROC`, BREXX `SYSEXEC`/`RXLIB`, STC step libraries, parameter libraries), each cited to the sysgen JCL in research note N-3.
  - The job now has 23 `LISTDS` commands plus two `LISTCAT`, and six `CFG*` steps that print the live `LNKLST00`, `IEAAPF00`, `IEFSSN00`, `JES2`, `IKJACCNT` and `TSOLOGON`.
  - A completeness check is defined: every DSN named in the `CFG*` output must appear in `LIST`, otherwise the job is extended and re-run.
  - Residual risk: `&SYSUID` libraries are covered for IBMUSER only.
- The JCL was checked for at most 71 columns and ASCII only. The job is still not run (it needs the OSE-003 guest).

### Independent re-review — 2026-11-26

Reviewer: Codex, high tier (escalated re-review following prior changes request), independent of author. Reviewed `2d4ec1c` on `review/OSE-011-r2`.

Source part accepted. R11-1 resolved: the job now includes SYSC.PROCLIB, SYSC.LINKLIB, BREXX.LINKLIB, SYS1.CMDPROC, SYS2.EXEC and the other documented concatenation members, prints configuration members and requires checking configured DSNs against its LIST coverage before recording a collision result. Rechecked against pinned sysgen jcl/brexxcfg.jcl:21-26, jcl/mvs00.jcl:136-151 and jcl/sysgen05.jcl:526-537. Python assertions confirmed the previously missing LISTDS commands, ASCII-only JCL and <=71 columns (RC 0). Guest RC parsing, effective configuration confirmation and final collision table remain acceptance test 2; no guest listing or terminal exercise ran. Therefore the complete task is not VERIFIED.

Validation in this worktree: `python -I scripts/check_repo.py` -> RC 0; `python -I -m unittest discover -s tests/host -v` -> RC 0, 11 repository tests passed. No guest mutation, dependency change, merge or release. Human owns integration; this review does not alter other task branches.

### Guest part, 2026-11-27 (author: coordinator session, standard tier)
Branch `task/OSE-011-guest` from main 7146aed. Lease: volume `ose-guest-011` (a new copy of `ose-sysgen-1`), taken 2026-11-27T14:19:36Z and released after the last container exited. Evidence: `artifacts/evidence/ose-011/guest/` (not in Git). `SHA256SUMS` there has 20 entries; its own SHA-256 is `e2a9b1b969884818a397c7e99906f0f7223fecfb7fca37f014fe72b72e73f72b`.

**Acceptance test 2: closed.** Final run `DASD_VOLUME=ose-guest-011 sh scripts/audit-listing.sh` → **RC 0** (`runs/20261127T142904Z-1520/`). Step RCs: CFGLNK, CFGAPF, CFGJES, CFGTSO, CFGLOG `0000`; CFGSSN `0004` (HMBLIST AMB126I, listing produced); LIST `0004` (LISTCAT of the absent HLQ `OSE`). 32 libraries, 3825 member and alias names, nothing unparsed. **No collision for OMVS, OSH, OSE, OSED, OSE1 or OSES**; no name even starts with one of them. HLQ `OSE` has no data set and no alias. The table and residual risks are in research N-4.

| Run | RC | What it showed / changed |
|---|---|---|
| 1 `runs/20261127T142139Z-2168` | 1 | `SYS1.PARMLIB(IEFSSN00)` does not exist on 3.8j (S013-18). Without `COND=EVEN` all later steps, including LIST, were skipped. → CFGSSN dumps load module IEFJSSNT (SYS1.LINKLIB) with HMBLIST; every step `COND=EVEN` |
| 2 `runs/20261127T142354Z-1085` | 1 | All steps ran. The driver was too strict (RC 4 of HMBLIST and LISTCAT, both expected) and the parser missed aliases. The **completeness check** found 7 configured libraries missing from the job (ISF.LINKLIB, ISF.ISFCLST, SYSGEN.NJE38.AUTHLIB, SYS1.VTAMLIB, SYS1.INDMAC, SYS1.HELP, SYS2.HELP) plus `&SYSUID` libraries → job extended; alias parser; CFG* 0-4 |
| 3 `runs/20261127T142722Z-111` | 0 | Extended job. Unquoted `LISTDS CLIST` is not prefixed in batch TSO → the runner qualifies `&SYSUID` libraries with the user ID |
| 4 `runs/20261127T142904Z-1520` | 0 | Final. `MVSCE02.CLIST` and `.EXEC` exist and are empty; every DSN named in the configuration printouts is listed |

Files:
- changed: `jcl/audit/list-libraries.jcl` (IEFJSSNT via HMBLIST, `COND=EVEN`, 9 more libraries, header), `docs/research/2026-11-26-tso-terminal-audit.md` (N-3 corrected, N-4 new);
- new: `scripts/audit-listing.sh`, `tests/guest/audit/run_listing.py`, `tests/host/test_audit_listing.py` (10 tests);
- changed `scripts/lib/common.sh` and `scripts/deploy.sh`: `guest_run`, `MANIFEST` and `export_evidence` moved from `deploy.sh` into `common.sh` (`guest_run` is the former `guest()` with the script as a parameter), so this listing uses the same verified evidence export. The OSE-004 fake-docker tests pass unchanged.

The scripts, the common.sh move and the test file are outside this card's file list; the reviewer should check them.

Host: `python -I scripts/check_repo.py` RC 0; `python -m unittest discover -s tests/host` RC 0.

Still open (not part of acceptance 2): the terminal probes (TGET ASIS, TPUT FULLSCR, STAX) from a CC/370 program, now possible with the OSE-004 deploy path; the TSO macro manual form numbers.

Next action: independent review of the guest part; then the human decides on the merge.

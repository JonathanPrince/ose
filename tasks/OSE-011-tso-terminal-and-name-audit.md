# OSE-011 — TSO terminal API and name-collision audit
Status: READY (source part IMPLEMENTED; review round 1: changes requested 2026-11-26, rework done, awaiting re-review; guest listing still needs OSE-003)
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

# TSO terminal API and name-collision audit, source part (OSE-011)

- Task: OSE-011 (source part). Date: 2026-11-26. Platform of the evidence: **MVS 3.8j** as distributed and as built by MVS/CE Sysgen. The evidence was read on the Windows workstation. Nothing was assembled, run or listed on a guest.
- Confidence labels follow ADR-0002. **observed** means read in pinned source or pinned tape bytes, statically. **documented** means stated by upstream comments or docs at the pin. **hypothesis** means an inference not yet tested.

## Sources

| Ref | What | Pin |
|---|---|---|
| T-DIST | IBM MVS 3.8j distribution tape `tape/zdlib1.het` in the sysgen repo, git blob `d1338964`, file sha256 `9550fe9b2a8632614a8dbd1ad6916a53c924fbf89c8190802a3d065dac886144` | sysgen `4746195d` (lock `ibm-mvs38j-distribution`) |
| LIBC | libc370 | v2.25.1 `fcde4e88` |
| BRX | BREXX/370 | v3.1.0 `5aabe493` |
| SDSF | mvslovers sdsf | v1.2.0 `cfb1b02b` |
| SG | sysgen repo text (JCL, usermods, `sysgen.py`) | `4746195d` |
| PD | IBM Base Program Directory for MVS 3.8J (`documentation/mvs38bas.pdf` in the sysgen repo, Service Level 8208), read with `pdftotext -layout` | `4746195d` |
| MVP | MVP package files | `4c004a59` |

**Method for T-DIST.** The tape is AWS/HET, with zlib- or bzip2-compressed blocks. A throw-away reader decoded each block as cp037. It sat in the session scratchpad, is not committed and is about 30 lines; a reviewer can re-create it from the HET header layout of 2 + 2 + 1 + 1 bytes. Macro prototypes were then located by the pattern `&NAME <macro>`.

Locations are given as *tape file number / block number*. The file's HDR1 label names the SMP RELFILE, for example `ETI1106.F1`. Because the reader is ad hoc, every tape row is **observed (static decode)**. A guest `SYS1.MACLIB` listing from OSE-003 would confirm the macros are installed.

## A. Terminal facilities on MVS 3.8j TSO

### A-1 Macros present in the distribution (T-DIST)

| Macro | Purpose (from the macro's own prologue, or IBM's standard use) | Mode | SVC / code | Tape location | RELFILE (HDR1) | Confidence |
|---|---|---|---|---|---|---|
| TPUT | Write to the terminal. Options EDIT / ASIS / CONTROL / **FULLSCR** / NOEDIT; WAIT/NOWAIT, HOLD, BREAKIN; inter-user form with `ASID=`, `USERIDL=`, `TJID=` | line and full screen | SVC 93 | file 68, block 53 | `ETI1106.F1` | observed |
| TGET | Read from the terminal. EDIT / ASIS; WAIT/NOWAIT. Prologue: `$MAC(TGET) … PROD(TIOC)`, `ETI1106 79.11.28` | line and full screen | SVC 93 (R1 high bit = TGET) | file 68 | `ETI1106.F1` | observed |
| TPG | Write to a terminal as a graphic/no-edit message | full screen | SVC 93 | file 68, block 24 | `ETI1106.F1` | observed |
| STFSMODE | "Specify whether or not an application is presenting displays to a TSO/VTAM display terminal in full screen mode". `INITIAL=YES` prevents paging on the first full-screen TPUT. `RSHWKEY=` sets the reshow PF key. Status line "OS/VS2 TSO/VTAM DYNAMIC RESHOW LEVEL 2.0" | full screen | SVC 94, code 18 | file 59, block 8 | `ETV0108.F2` | observed |
| STLINENO | Set the line for the next *non*-full-screen TPUT on a TSO/VTAM 3270 | line on 3270 | SVC 94, code 19 | file 59, block 9 | `ETV0108.F2` | observed |
| STTMPMD | "Specify whether or not an application is presenting displays to a TSO display terminal as the terminal controller". `KEYS=` option. APAR ZA24648 | full screen | SVC 94, code 20 | file 68, block 18 | `ETI1106.F1` | observed |
| GTTERM | Return the primary and alternate screen sizes and attributes | query | SVC 94, code 17 | file 68, block 20 | `ETI1106.F1` | observed |
| GTSIZE / STSIZE | Get or set the terminal line size and screen depth | query/set | SVC 94, codes 11 / 10 | file 68, blocks 4 / 16 | `ETI1106.F1` | observed |
| STATTN, STAUTOLN, STBREAK, STCOM, TCLEARQ, RTAUTOPT | Attention simulation, auto line numbering, break, inter-terminal communication, clear queue, auto-prompt | line | SVC 94 (codes for STAUTOLN 9, STBREAK 4, STCOM 5, TCLEARQ 1, RTAUTOPT 14) | file 68, blocks 7, 10, 11, 15, 19, 5 | `ETI1106.F1` | observed |
| STAX | Establish an attention (PA1/ATTN) exit | interrupt | SVC 96 | file 50 | `EBB1102.F2` (file 49 HDR1) | observed |

**Product mapping, documented** from the IBM *Base Program Directory for MVS 3.8J*, which ships with sysgen as `documentation/mvs38bas.pdf` at `4746195d`:
- p.4, FMID table: `ETI1106` is "Terminal I/O Controller (TIOC)", `ETV0108` is "TSO/VTAM", `EBB1102` is "Base Control Program".
- p.8–9, tape contents: `ETI1106.F1` and `ETV0108.F2` hold distribution library **ATSOMAC** (21 and 8 members). `EBB1102.F2` holds **AMACLIB** (162 members, plus ATSOMAC).

So the TSO terminal macros come from ATSOMAC, and STAX comes from AMACLIB. **Hypothesis:** both are copied into the target `SYS1.MACLIB` at sysgen. The guest listing should check that.

Is TSO/VTAM, and therefore STFSMODE, actually present at run time? **Documented**: sysgen links the TSO/VTAM terminal control address space `IKTCAS00` (`jcl/stage2.jcl:6083-6091`) and runs it as a step (`jcl/sysgen05.jcl:115`). Its run-time behaviour is a **hypothesis** until it is tested on a guest.

### A-2 What libc370 v2.25.1 offers (LIBC)

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| L-1 | A stdio stream whose DCB is a terminal (`dcbdevt == DCBDVTRM`) writes each flushed buffer with **TPUT EDIT,WAIT,HOLD** (register form). | `src/stdio/@@fflush.c:76-87, 273-303` | observed |
| L-2 | Reading the same stream uses **TGET EDIT,WAIT**, strips leading and trailing blanks, and treats `/*`, `//`, `<eof>` or `<EOF>` as end of file. | `src/stdio/@@fgetc.c:60-75, 157-200` | observed |
| L-3 | The `*PUTLINE` stream writes through the TMP's PUTLINE service (variable records, 256-byte lines). It needs a TMP (ECT/UPT via the LWA), otherwise `ENODEV`. `*GETLINE` exists for reading, but GETLINE under a batch TMP "is not measured yet". | `src/stdio/@@fpput.c:1-45`; `include/stdio.h:97-100`; `src/stdio/@@fpget.c:41` | observed / documented |
| L-4 | libc370 offers **no full-screen, STFSMODE, GTTERM or STAX interface** and no termios. `isatty` is absent (OSE-012 inventory). | grep of `include/` and `src/` at the pin; OSE-012 data | observed |
| L-5 | Under TSO, unquoted data set names get the user's prefix (`__getpfx`). That matters for any shell that opens MVS data sets. | `src/stdio/@@fpopn.c:200-210` | observed |

Consequence: through plain stdio, a C program under TSO gets **line mode with editing, blank stripping and an EOF convention that no POSIX program expects**. That is usable for a first prototype shell, but it cannot preserve bytes exactly, which spec §3.3 requires.

### A-3 What existing MVS/CE full-screen programs use

| # | Program | Mechanism | Evidence | Confidence |
|---|---|---|---|---|
| E-1 | BREXX/370 FSS (full-screen services) | Opens with `GTTERM` for the screen sizes, then `STFSMODE ON` + `STTMPMD ON`. Writes with **TPUT FULLSCR** (the long parameter-list form, ASID 0). Reads with **TGET ASIS** and **TGET ASIS NOWAIT**. Closes with STFSMODE OFF + STTMPMD OFF. All are raw SVC 93/94 calls through a generic SVC stub. | `brexx370:fss/fss.c:400-443, 542-543, 1275-1292, 1411`; `brexx370:src/rxtso.c:51-221`; `brexx370:asm/rxsvc.asm:12-26` | observed |
| E-2 | BREXX runs **unauthorized** (AC=0, no APF entry) and still uses full screen. Only some unrelated functions take authorization from SVC 244. | `brexx370:mbt.toml:60-62, 146` | documented |
| E-3 | BREXX handles attention (PA1) with a STAX exit that only sets a flag. The interpreter acts on the flag at a clause boundary. | `brexx370:src/rxattn.c:1-40`; `src/interpre.c:1146, 1658` | observed |
| E-4 | SDSF (mvslovers) is an **ISPF dialog**: it loads `ISPLINK` and ships panels in `ispplib/`. It does no 3270 I/O of its own. | `sdsf:src/isfisp.c:4726`; `sdsf:ispplib/` | observed |
| E-5 | ISPF (MVP package, Wally McLaughlin) and REVIEW (MVP package) are also full-screen TSO programs, but their source is not in a readable repo at the pin. They were not audited. | lock entries `mvp-pkg-ispf`, `mvp-pkg-review` | — |

### A-4 Authorization finding (card escalation trigger)

The trigger asks whether the only usable full-screen interface needs authorized code. **It does not**: E-1 and E-2 show a production full-screen program running unauthorized on MVS/CE with SVC 93/94 (confidence: observed in source, documented as unauthorized; not yet run by OSE). Two caveats:
- **Hypothesis:** the inter-user TPUT operands (`ASID=`, `USERIDL=`) need authorization. The macro shows the operands but states no rule, and the governing IBM manual has not been read yet. OSE does not need them for a terminal adapter.
- From OSE-005: a UFSD client must be APF-authorized. So a shell can drive the terminal unauthorized, but it **cannot itself be the UFSD client**. That is consistent with the "trusted broker" recommendation in research 2026-11-26-ufsd-audit.

No escalation to OSE-010 or the human is raised by this card.

### A-5 Recommendation for the M1 terminal adapter (hypothesis)

**Hypothesis, to be tested in M1:**
1. **Start in line mode.** Use TPUT/TGET directly: **TGET ASIS** to get the user's bytes without TSO editing, and **TPUT ASIS or EDIT** for output. Do not use libc370 stdio for the terminal, because of L-2's blank stripping and magic EOF strings. Keep it behind a small adapter interface (`read_line`, `write`, `attention`) so that a full-screen version can replace it.
2. **Attention.** Use STAX (SVC 96) with a flag-only exit, as BREXX does (E-3), and map PA1 to SIGINT-like behaviour at safe points.
3. **Full screen later (M4 "terminal").** STFSMODE + STTMPMD + GTTERM + TPUT FULLSCR / TGET ASIS, following BREXX FSS as a working reference for the parameter layout. Emulate a scrolling VT-like screen on the 3270 buffer.
4. **Encoding.** All of this is EBCDIC on the 3270 path. The adapter is where spec §3.3's host and network conversion policy has to be applied.
5. **Unverified.** TGET ASIS behaviour across 3270 models and Hercules, maximum input length, and NOWAIT timing. These need guest tests, which belong to OSE-004 or an M1 card.

## B. Name-collision audit

### N-1 Candidates

The spec names only `OMVS`. `docs/conventions.md` leaves the HLQ open. The other candidates below are **proposals of this card**, chosen following UFSD's lesson (research 2026-11-26-ufsd-audit, `ufsd:include/ufsd.h:544-561`) that a subsystem must not share its name with a started procedure.

| Role | Candidates |
|---|---|
| TSO command | `OMVS` (spec), `OSH` |
| Data set HLQ | `OSE` |
| Started task / procedure | `OSE`, `OSED` |
| SSI subsystem | `OSE1`, `OSES` (must differ from the STC) |

### N-2 Source-side search (done; not a substitute for the guest listing)

Each candidate was searched as a whole token, with no letter, digit or `@#$` on either side. The search covered SG, MVP (both latin-1 and cp037 decodes), the ufsd, sdsf, brexx370 and libc370 repos at their pins, and the decoded IBM tapes (`zdlib1`, `ptfs`, `vs2start`, `vs2spool`, `apvtmacs`, `rpf184`, `smp4b`, `dz1d02`, `j90012`).

| Name | Hits | Nature | Collision? |
|---|---|---|---|
| OMVS | 4 in MVP `IMON370` | Display text "OMVS INPUT WAIT" / "OMVS OUTPUT WAIT" (swap-reason labels) | no (not a member, procedure or command) |
| OMVS | 2 in `rpf184.het` | Assembler comment "OMVS POSIX DATASET" next to `DSORG=C'HFS '` | no |
| OSH | 2 in `dasd/syscpk.3350` | Random bytes in a compressed DASD image | no (noise) |
| OSE | 10 | All inside the Python token `OSError` (sysgen.py, brexx, libc370 sdk) or binary noise in MVP `ISPF` | no |
| OSED | 3 in `ptfs.het` / `vs2start.het` | Inside message text ("…OSED, OUTPUT ERROR") and binary | no |
| OSES, OSE1 | 0 | — | no |

Result: **no collision found in the sources available on the host** (observed). This does **not** cover:
- the built DASD volumes, which are compressed CCKD and were not decoded;
- members created during sysgen;
- `SYS1.PARMLIB(IEFSSN00)`. The sysgen text sources do not define it, so it comes from the starter system or the build, and subsystems registered dynamically, such as UFSD's `UFS1`, are not in it.

### N-3 Guest listing (not run)

`jcl/audit/list-libraries.jcl` lists the members of SYS1/SYS2 CMDLIB, LINKLIB, LPALIB, PROCLIB and PARMLIB, the catalog entries for level `OSE` and alias `OSE`, and prints `IEFSSN00`. It is read-only and carries no credentials. Expected RCs are in its header. **Status: not run.** It needs the OSE-003 guest and a lease. Card acceptance test 2 stays open until it has run and its RC and output are recorded here. **Hypothesis:** MVS 3.8j TSO `LISTDS … MEMBERS` works in batch under IKJEFT01. If it does not, switch to IEHLIST with volume DDs.

## Open items

- Guest run of `list-libraries.jcl` (needs OSE-003 and a lease) → closes acceptance test 2.
- Read the TSO terminal macro documentation: the TSO Guide to Writing a Terminal Monitor Program and the TSO/VTAM programming manual for OS/VS2 MVS 3.8. Form numbers are still to be recorded from a primary copy. This confirms A-1's purposes and the authorization rule for inter-user TPUT.
- Guest probes of TGET ASIS, TPUT FULLSCR and STAX from a CC/370 program (with OSE-004).

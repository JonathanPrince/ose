# OSE-004 — CC/370 + MBT hello compile/deploy harness
Status: VERIFIED (host portion previously accepted and merged; guest re-review of c76f088 accepted 2026-11-27; human merge pending)
Milestone: M0
Dependencies: OSE-002 (host compile); OSE-003 (guest run; a coordination dependency not listed in BOOTSTRAP)
Owner: author model (standard tier)
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-004-hello-harness
Guest resources: lease required for deploy and run
Baseline commit: 5970f87 (main)

## Goal and non-goals
Goal: compile and link a C "hello" on the host with the pinned CC/370 and MBT (spec §2 prefers host compilation). Deploy the load module to the guest, run it as a batch job and as a TSO command, and capture RC and output automatically. Record the observed C dialect and linkage facts.
Non-goals: POSIX functions, UFSD access, a new toolchain.

## Inputs and primary references
mvslovers/cc370, libc370 and mbt at their pins, and their docs at mvslovers.readthedocs.io. How MBT deploys to the guest must come from MBT source and docs. Do not assume a transport. If it uses FTPD or mvsMF, say so, because OSE-007 treats those as alternate access paths.

## Allowed files / interfaces
`Makefile` (build, deploy), `scripts/build.sh`, `scripts/deploy.sh`, `src/utils/hello/` (test program only), `jcl/hello/*`, `tests/guest/hello/*`, `docs/runbooks/hello-compile-deploy.md`, `docs/research/YYYY-MM-DD-toolchain.md`, this card.

## Acceptance tests (commands and expected outcomes)
1. `make build` → RC 0. Record the toolchain version string and the sha256 of the object and the load module.
2. `make deploy` → RC 0. The member's presence on the guest is confirmed by a listing job, not by the deploy tool's exit code.
3. Batch run: the step RC equals the program's return value (test a planted value such as 4 as well as 0), and the output DD contains the exact expected string. Both are parsed from spool.
4. A TSO invocation shows the same output.
5. Toolchain note covering: compiler version, C dialect observations (C89 features, `long long`, inline asm, varargs), entry linkage, AMODE/RMODE of the output, reentrancy options, and the EBCDIC code page in use. Each item is labeled observed or documented.

## Escalation triggers
- The compiler cannot handle a construct that OSE-012 marks as required → record it and escalate to OSE-010. The spec §5 gate says to adapt the source, not replace the toolchain.
- Runtime ABEND → record the completion code and PSW; escalate after two failed attempts.

## Handoff
- Changed files / commits:
  - New: `scripts/build.sh`, `src/utils/hello/hello.c`, `docs/research/2026-11-26-toolchain.md` (with addendum T-7), `docs/runbooks/hello-compile-deploy.md`.
  - Changed: `Makefile` (`build` target), `dependencies.lock.json` (adds `maclib370`, approved by the human 2026-11-26, option a), `docs/research/2026-11-26-licensing.md` (addendum, question 10), the runbook and research indexes, `docs/status.md`, `tasks/usage.jsonl`, this card.
  - Branch `task/OSE-004-hello-harness`: commit 16565eb (blocked state), then the link commit.
- Commands run, RC, evidence paths (all under `artifacts/evidence/ose-004/`):
  - Toolchain: `sh scripts/build.sh toolchain` gave RC 1 three times (missing flex/bison; no git in the image, so no version stamp; libcc370rt not built), then RC 0. Versions `cc370/as370/ld370 1.6.3 (802dde1)`. maclib370 `extract.py --verify`: 1035/1035, RC 0.
  - libc: `sh scripts/build.sh libc` → RC 0, `libc.a` `d3a422e8…`.
  - hello: `sh scripts/build.sh hello` → RC 0, `HELLO` `81757408…`, `HELLO.xmit` `0e69e9fa…`. Byte-identical across runs once the timestamps were pinned (research T-7).
  - **Acceptance 1: `make build` (GNU Make 4.2.1) → RC 0** after a clean rebuild of everything. The same hashes came out twice.
  - Probes: `PROBE_DIR=… sh scripts/build.sh probes` (research T-4).
  - `python scripts/check_repo.py`: RC 0. Host unittest: RC 0.
- Tests not run and why:
  - Acceptance 2–4 (deploy and confirmation listing, batch RC/output with a planted RC 4, TSO run) are not run: no guest (OSE-003), no lease, and the deploy transport is undecided (mbt uses mvsMF over HTTP Basic, an alternate access path for OSE-007).
  - Acceptance 5: compile-time and link-time facts are recorded (T-4, T-5, T-7). The runtime dialect checks need the guest.
- Decisions / ADRs: human decision 2026-11-26: option (a), maclib370 v1.0.0 `e85286a7` added to the lock. No ADR.
- Known defects / blockers:
  - The macros are TK5-derived; that they work on MVS/CE needs a guest run.
  - The licence of the macro content is UNRESOLVED (licensing question 10).
  - The OSE-012 probe `p04` has a raw newline in a string literal; the fix belongs on the OSE-012 branch.
  - Debian packages are not snapshot-pinned.
- Next action: standard-tier review of the host part. After OSE-003: choose a deploy transport, write `scripts/deploy.sh`, `jcl/hello/*` and `tests/guest/hello/*`, then run acceptance 2–4 under a lease.
- Usage/cost if available: not metered.

### Guest part, 2026-11-27 (author: coordinator session, standard tier)
Branch `task/OSE-004-guest` from main 3658ace (OSE-003 merged). Lease: volume `ose-guest-004`, a copy of `ose-sysgen-1`, taken 2026-11-27T12:07:47Z and released after the last container exited. Evidence: `artifacts/evidence/ose-004/guest/` (not in Git). `SHA256SUMS` there has 64 entries; its own SHA-256 is `f3c47c45943cbf7c3906a69b0bd01a8f6a998ac0de306aae155424f97f0d514e`.

**Deploy transport decision (T-6):** a binary EBCDIC deck to the card reader `001A` (port 3506). It carries the XMIT in-stream behind `DD DATA,DLM=`; IEBGENER stages it and TSO RECEIVE (NJE38 v2.3.0) unpacks it. This is the same method upstream sysgen uses for its mvslovers products. **No FTPD and no mvsMF**, so none of the OSE-007 alternate access paths is used. No new dependency.

New files: `scripts/deploy.sh` (`deploy|run|all`), `tests/guest/hello/hello_guest.py` (guest driver; it reuses the OSE-003 `mvs-smoke.py` and `tso-smoke.py` unchanged), `jcl/hello/deploy.jcl`, `list.jcl`, `run.jcl`, and `tests/host/test_hello_guest.py` (13 host tests). Changed: `Makefile` (`deploy`), the runbook and research T-8.

| Acceptance | Command | RC | Result |
|---|---|---|---|
| 1 build | (host part, merged 2026-11-26) | 0 | `HELLO.xmit` `0e69e9fa…`; `deploy.sh` refuses any other hash |
| 2 deploy + listing job | `DASD_VOLUME=ose-guest-004 sh scripts/deploy.sh deploy`, 5 times | 0 ×5 | OSEHDEP: DELOLD, STAGE, RECV, CLEANUP `0000`, GONE `0004` (in the last 3 runs; step added after the anomaly below). The separate listing job OSEHLST, `LISTDS 'MVSCE02.OSE.LOAD' MEMBERS`, lists `HELLO`. RECEIVE: "Receive into 'MVSCE02.OSE.LOAD' successful"; IEBCOPY `IEB167I` member loaded |
| 3 batch | `sh scripts/deploy.sh run`, 4 times | 0 ×4 | OSEHRUN: step RC0 `0000`, step RC4 (`PARM='4'`) `0004`. SYSPRINT lines exactly `OSE-004 HELLO RC=0` and `OSE-004 HELLO RC=4`, parsed from the JES2 printer file |
| 4 TSO | inside each `run` | 0 ×4 | logon MVSCE02, `CALL 'MVSCE02.OSE.LOAD(HELLO)' '7'` shows `OSE-004 HELLO RC=7` then `READY`, with no `ALLOC` needed; logoff |
| 5 toolchain note | research T-8 | — | runtime: entry and RC propagation, PARM, stdout routing (batch and TSO), printf varargs, transport code page cp037, TK5 macros at runtime (only the paths hello uses); AMODE/RMODE not applicable. Each item labelled |
| final clean run | `sh scripts/deploy.sh all` | 0 | `runs/20261127T123005Z-1887/` |
| host | `python -I scripts/check_repo.py`; `python -m unittest discover -s tests/host` | 0, 0 | see the commit; 13 new tests |
| regressions after moving `tools_image` into `common.sh` | `sh scripts/doctor.sh`; `sh scripts/smoke.sh ipl1` (×2) | 0, 0 | |

Every IPL shut down cleanly under the OSE-003 rules (`$HASP099` → `$HASP085` → `IEE334I` after the request, Hercules RC 0). The MVSCE02 password is read from `users.conf` at run time; a grep of every saved file finds it nowhere.

**Anomaly (open, guarded):** on the second deploy (guest time 07:12), the IDCAMS DELETE of the existing `MVSCE02.OSE.LOAD` reported `IKJ56228I … NOT IN CATALOG OR CATALOG CAN NOT BE ACCESSED`, and RECEIVE then wrote into the existing library. With identical bytes the test passed, but a stale module could have passed the same way. A diagnostic job found the library correctly cataloged (UCPUB000, via the MVSCE02 alias). The same DELETE worked in that job and in both later re-deploys. Cause unknown. **Fix:** a new step GONE must see the target gone (`LISTCAT` CC 4), or STAGE, RECV and CLEANUP are skipped and the deploy fails. Covered by host tests.

**Incident (my error):** a regression `smoke.sh ipl1` exported into the fixed `artifacts/evidence/ose-003/smoke/` and overwrote 9 of the 47 checksummed OSE-003 evidence files (4 with the new IPL, 5 with copies inherited from the rework run in the volume). No copy of the originals survives. `SHA256SUMS` is left as it was, so it reports them FAILED, and the facts are in `artifacts/evidence/ose-003/INCIDENT-2026-11-27-overwrite.md`. The content had been independently verified (OSE-003 review r1: 47/47) and is reproduced in `run2/`, `rework-r1/` and the reviewer's evidence. **Fix in this branch:** `smoke.sh` and `deploy.sh` export each invocation to a new directory that must not exist yet, and `smoke.sh` empties the volume's smoke directory first. This touches the merged OSE-003 `smoke.sh`, outside this card's file list; the reviewer should check it.

Scope note: outside the card's list are `scripts/lib/common.sh` (`tools_image` and `creds` moved there unchanged from `smoke.sh`, with the tag now computed on call), `scripts/smoke.sh` (the move and the evidence fix), `docs/runbooks/sysgen-and-ipl.md` (evidence path), `tests/host/test_hello_guest.py`, and the incident note in the OSE-003 card.

Not run: the OSE-012 runtime probes on the guest; the TSO return code of `CALL` (TSO does not display it).

Next action: independent review of the guest part, including the `smoke.sh` and `common.sh` changes and the incident; then the human decides on the merge.

## Independent review and gate result

### Independent review — 2026-11-26

Reviewer: Codex, standard tier, independent of author. Reviewed 419fa79 against 5970f87 in isolated review/OSE-004-r1. Result: **changes requested**.

- **P2 / R04-1 — Host build fails from a Git worktree bind-mounted into Docker.** `scripts/build.sh:71` runs `git config --global --add safe.directory /tmp/cc370` while the container's current directory is `/ose`. A worktree has a `.git` file pointing to its host-side Git metadata; that path does not exist inside this bind mount. This Git invocation tries to resolve the repository and fails before the source is copied or compilation starts. Reproduced on the requested review branch with `& 'C:/Program Files/Git/bin/sh.exe' scripts/build.sh all`: RC 1, `fatal: not a git repository: /ose/C:/Users/49170/projects/ose/.git/worktrees/OSE-004-r1`, then `build.sh: toolchain build failed`. Docker access was approved, and the source caches were isolated copies at the correct pins. Run the global Git configuration from a directory outside the worktree (for example `git -C /tmp config --global ...`), or otherwise avoid resolving the host worktree metadata, and add a worktree smoke check. This blocks the normal host command in this valid checkout layout; it is independent of the compiler and linker.
- Validation: `python -I scripts/check_repo.py` -> RC 0; `python -I -m unittest discover -s tests/host -v` -> RC 0, 11 tests passed. These structural tests do not exercise Docker worktree support.
- To separate R04-1 from compiler correctness, exported unchanged 419fa79 with `git archive --format=zip` into this worktree's ignored `artifacts/standalone/`, copied the three pinned source caches there, and ran the same `sh scripts/build.sh all` in the export. Results are recorded below on completion. This alternative verification does not close R04-1.
- No deploy, listing, guest batch/TSO execution or guest mutation was performed. Acceptance 2-4 and TK5-macro compatibility remain pending OSE-003 and a lease. The review does not certify M0 hello execution or the runtime ABI.

Exported-tree build result: `& 'C:/Program Files/Git/bin/sh.exe' scripts/build.sh all` -> **RC 0**, using the pinned Debian image and copied cc370/libc370/maclib370 caches. Fresh build produced cc370/as370/ld370 1.6.3 (802dde1); macro verification 1035/1035. SHA-256 of libc.a, hello.o, HELLO and HELLO.xmit independently match all four expected full hashes in the runbook (Python hashlib assertions, RC 0). Logs, version strings, file370 decodes and hash files are in `artifacts/review/OSE-004-r1/artifacts/standalone/artifacts/evidence/ose-004/` relative to the main workspace. This confirms the compilation/linking claims in a standalone export, while the normal worktree command still fails R04-1. The guest-dependent tests remain not-run. Next action: fix R04-1 and rerun the normal worktree build; retain the guest gate separately.

### Author rework for R04-1 (2026-11-26)
- **Accepted and reproduced.** A fresh detached worktree (`artifacts/wt-ose004`) has `.git` = `gitdir: C:/Users/…/.git/worktrees/wt-ose004`. In the container, `git config --global --add safe.directory /tmp/cc370` with cwd `/ose` → `fatal: not a git repository: /ose/C:/Users/…/worktrees/wt-ose004`, RC 128. The same command run from `/` → RC 0.
- **Fix:** `scripts/build.sh` now runs that one command as `(cd / && git config --global …)`. No other git call inside the container resolves `/ose`: cc370's `mkversion.sh` and libc370's `mklibc.py` use `git -C` on their copied clones under `/tmp`, and maclib370's `extract.py --verify` does not call git.
- **Worktree smoke check:** `sh scripts/build.sh all` run inside the fresh worktree → **RC 0** (about 4 min, with its own pinned clones). It reproduced every recorded hash: `libc.a` `d3a422e8…`, `hello.s` `866cd302…`, `hello.o` `1a1001c4…`, `HELLO` `81757408…`, `HELLO.xmit` `0e69e9fa…`. The main-tree `sh scripts/build.sh hello` gives the same hashes. The worktree was removed afterwards. The check is now a repeatable step in `docs/runbooks/hello-compile-deploy.md`.
- `python scripts/check_repo.py`: RC 0. Host unittest: RC 0.

### Independent re-review — 2026-11-26

Reviewer: Codex, high tier (escalated re-review after previous changes request), independent of author. Reviewed `0d13ac2` against `59d3b63` on `review/OSE-004-r2`, using the existing worktree at `artifacts/review/OSE-004-r1`. **Host portion accepted; R04-1 closed. No new findings.** The complete task remains REVIEW because guest acceptance 2-4 are still open.

- Confirmed the worktree root `.git` is a file referencing host-side metadata. The fix runs global Git configuration from `/`, avoiding discovery of `/ose/.git`. The runbook now gives a reproducible worktree smoke command.
- Independently ran `& 'C:/Program Files/Git/bin/sh.exe' scripts/build.sh all` in this worktree with the isolated, pinned source caches and approved Docker access: **RC 0**. This is the exact recipe underlying `make build`; no exported-tree workaround or source edits were used. CC/370, as370 and ld370 report 1.6.3 (802dde1); macro verification passed 1035/1035. Compiler/runtime, libc, hello object, load module and XMIT all built successfully.
- Independently recomputed SHA-256 with Python hashlib: all five expected hashes match, including libc.a d3a422e8..., hello.s 866cd302..., hello.o 1a1001c4..., HELLO 81757408... and HELLO.xmit 0e69e9fa.... Full values are in the existing T-7 table and output files. Evidence: `artifacts/review/OSE-004-r1/artifacts/evidence/ose-004/` relative to the main workspace (build logs, macro check, versions, hashes and file370 decodes). Hash assertions returned RC 0.
- `python -I scripts/check_repo.py` -> RC 0; `python -I -m unittest discover -s tests/host -v` -> RC 0, 11 tests passed; `git diff --check` -> RC 0 before recording this review.
- Deploy, guest listing, planted batch RC/output, TSO invocation and TK5 macro/runtime compatibility remain not-run, pending OSE-003, a guest lease and deploy-transport decision. No guest mutation, dependency change, merge or release. Next action: human integration of the accepted host work; complete acceptance 2-4 when the guest is ready.

### Independent guest review — 2026-11-27

Reviewer: Codex, standard tier, independent of author. Reviewed `9a57b02` against `3658ace` on `review/OSE-004-guest-r1`, worktree `artifacts/review/OSE-004-guest-r1`. **Changes requested; positive guest acceptance 2–4 independently passed.** No implementation changes, merge or push.

- **R04G-1 [P2], `jcl/hello/deploy.jcl:33` (also line 40): the GONE guard does not prevent downstream execution.** On the actual OSE-003 MVS/CE reviewer build (MVS 3.8j), a harmless IEFBR14 job with the same conditions produced DELOLD=0000, GONE=0000, STAGE bypassed (`IEF202I`/`IEF272I`), but RECV=0000 and CLEANUP=0000. A condition referring to a bypassed step did not suppress the next step. Thus the documented guarantee that all three steps are skipped when the old library survives is false. The Python driver rejects the overall run, but it does so after RECEIVE has been attempted; with leftover staging data it can still receive into the old library. Repeat the prerequisite conditions directly on RECV and CLEANUP (or use a target-supported equivalent) and add a negative guest test with GONE=0 proving all three steps are bypassed. The diagnostic substitutes IEFBR14 for the programs; it establishes condition behavior, not the cause of the original DELETE anomaly.
- **R04G-2 [P2], `scripts/deploy.sh:46–50`: evidence export failure is discarded.** A local mocked Docker call returned 23 for the evidence copy after guest RC 0; `sh scripts/deploy.sh run` still returned 0. The new run directory then lacks result JSON and spool/terminal proof. The next invocation deletes `/work/evidence/ose-004/<mode>`, so the only complete copy can be lost. Propagate capture/export failures and retain recoverable guest evidence until export succeeds; verify required evidence exists before success. `smoke.sh` has the same ignored-export pattern and should use the same handling. This is material to the evidence preservation incident fix.

Validation and evidence (all paths below relative to this review worktree):

| Command/check | RC | Result |
|---|---|---|
| `python -I -m unittest discover -s tests/host -v`, `OSE_BASH=C:/Program Files/Git/bin/bash.exe` | 0 | 63 tests: 54 passed, 9 skipped (source caches absent); `artifacts/evidence/review-ose-004/host-tests.txt` |
| `python -I scripts/check_repo.py` | 0 | repository check passed |
| `PYTHON=python DASD_VOLUME=ose-review-004-20261127 sh scripts/deploy.sh all` | 0 | deploy/list HELLO passed; batch RC0=0000 and RC4=0004 with exact output; TSO plain CALL7 output and logoff passed; evidence `artifacts/evidence/ose-004/guest/runs/20261127T131220Z-535/`, wrapper log and RC in `artifacts/evidence/review-ose-004/` |
| `docker run --rm --name ose-review-cond-004 --user 1000:1000` with worktree `/ose:ro`, evidence `/out`, leased volume `/work`, tools image `ose-hercules:4.9.1-ee86c4de-tools-834605f5b6b7`, `python3 -I /out/cond-review.py` | 0 | R04G-1 reproduced; redacted deck, raw spool, result, console and shutdown log in `artifacts/evidence/review-ose-004/cond-*` |
| `bash artifacts/evidence/review-ose-004/export-failure.sh` (mock only; no actual Docker calls) | 0 (incorrect) | R04G-2 reproduced: simulated copy RC 23 discarded; fixture/output retained |
| Python SHA-256 verification of author manifests | 0 | OSE-004: 64/64 match, manifest hash f3c47c45943cbf7c3906a69b0bd01a8f6a998ac0de306aae155424f97f0d514e. OSE-003: exactly the 9 disclosed mismatches among 47; no additional mismatches; `author-manifests.json` |

Lease acquired before cloning or running; author volumes never mounted. Disposable `ose-review-004-20261127` copied from stopped reviewer baseline `ose-sysgen-review-003-20261127`. Three cold IPLs, each with ordered shutdown messages after the request, Hercules RC 0 and no forced quit. All containers stopped, lease released; reviewer volume retained stopped. The independently built HELLO.xmit from the accepted host review was used after verifying its full recorded hash. Acceptance 1 was not rebuilt in this guest review. T-8 appropriately limits runtime macro/varargs claims to HELLO's paths; it must correct the skipped-step claim with R04G-1. The tools/credentials helper move and per-run export destination are reasonable scope extensions for this harness. The overwritten OSE-003 originals remain damaged as disclosed; their manifest was not rewritten. Prior independent OSE-003 evidence is separate and preserved.

Next action: fix R04G-1/R04G-2, add the failure-path checks, and request re-review; escalate rework one tier per task conventions. Do not mark VERIFIED yet.

Review evidence sealed: `artifacts/evidence/review-ose-004/REVIEW-SHA256SUMS`, 32 files, manifest SHA-256 `1ce2cc9214136e98115346692d5c0f7ec859ad51eae532c4c5c3559bc25aa504`. Credential scan of reviewer evidence and guest exports: RC 0, no password found. Final `docker ps` empty and shared checkout clean after lease release.

### Rework after review r1 (R04-2, R04-3), 2026-11-27, author
Baseline: review/OSE-004-guest-r1 at 8e9486c (fast-forwarded). Lease on `ose-guest-004`, taken 13:24:51Z and released after the last container exited. Evidence: the new runs under `artifacts/evidence/ose-004/guest/runs/` are covered by `SHA256SUMS-rework-r1` (26 entries; its own SHA-256 is `89858afb8ea23756663b0b3c5dd416e1dba2746c0e0bbb5bf1383d88b523fd94`). The first-round `SHA256SUMS` (64 entries, `f3c47c45…`) is unchanged: a failed command of mine truncated it, and it was rebuilt byte for byte from the unchanged files (same SHA-256 as recorded above, `sha256sum -c` all OK). A stray directory that the fake-docker test created when run against the reviewed `deploy.sh` was removed after inspection; it held only fake content.

| Finding | Fix | Evidence |
|---|---|---|
| R04-2: GONE=0 skipped STAGE, but RECV and CLEANUP still ran (MVS ignores a COND test that names a bypassed step) | `deploy.jcl`: RECV `COND=((0,NE,DELOLD),(4,NE,GONE),(0,NE,STAGE))`; CLEANUP adds `(0,NE,RECV)`. Both lines fit in 71 columns | Host tests: both steps test DELOLD and GONE; JCL columns; the stale variant drops only the target DELETE. **Guest negative test** `sh scripts/deploy.sh stale` (new driver mode `deploy-stale`: a normal deploy, then OSEHSTL without the target DELETE): RC 0. GONE `0000`; `IEF202I OSEHSTL STAGE/RECV/CLEANUP - STEP WAS NOT RUN BECAUSE OF CONDITION CODES` and `IEF272I … NOT EXECUTED.`; executed steps only DELOLD and GONE; RECEIVE count 1 before and after (`runs/20261127T132830Z-409/`) |
| R04-3: `deploy.sh` succeeded when the evidence export failed | Per-invocation guest copy `/work/evidence/ose-004/runs/<id>/<mode>`, no longer deleted at the start of the next run. After `cp -R`, sha256 manifests of both copies are compared. A failed `docker logs`, a failed copy, a failed hash, an empty or differing manifest: each prints `EVIDENCE: …`, keeps the guest copy and makes `deploy.sh` exit nonzero. The guest copy is deleted only after a match. `smoke.sh` got the same treatment: a per-invocation guest directory instead of emptying `/work/evidence/smoke`, and export failure gives RC 1 | Host tests drive the real `deploy.sh` with a fake `docker`: copy fails → RC ≠ 0, guest copy kept; incomplete copy → RC ≠ 0, kept; verified copy of 2 files → RC 0, then deleted. The verified test fails against the reviewed `deploy.sh`. **Found by the new check on the guest:** the first `stale` run (`runs/20261127T132452Z-553/`) reported a mismatch. The cause was Windows Python's `print` joining manifest lines with CRLF; Git Bash strips only the trailing CR, which is why the single-file fake test had missed it. The manifest now writes LF bytes, and the fake uses two files. That run's guest copy is kept in the volume; its host copy is complete (manifests equal apart from line endings). Later exports verified 4, 4 and 10 files |

Reruns after the fixes, all on `ose-guest-004`: `deploy.sh stale` RC 0; `deploy.sh all` RC 0 (deploy: GONE `0004`, then STAGE, RECV and CLEANUP `0000`, listing shows HELLO; run: `0000`/`0004`, exact SYSPRINT lines, TSO `RC=7`); `smoke.sh ipl1` RC 0 (per-run guest directory). Host: `python -I scripts/check_repo.py` RC 0; `python -m unittest discover -s tests/host` RC 0.

Next action: re-review of R04-2 and R04-3; then the human decides on the merge.

### Independent guest re-review — 2026-11-27

Reviewer: Codex, high tier (escalated after the first guest review). Reviewed `c76f088` against `8e9486c` on `review/OSE-004-guest-r2`, separate worktree `artifacts/review/OSE-004-guest-r2`. **Accepted; R04G-1 and R04G-2 closed; no new findings.** The author's R04-2/R04-3 names refer to those same findings. OSE-004 is VERIFIED, with its host portion accepted earlier. No merge or push.

- **R04G-1 closed:** RECV and CLEANUP now repeat DELOLD/GONE prerequisites. Independently ran `PYTHON=python DASD_VOLUME=ose-review-004-r2-20261127 sh scripts/deploy.sh stale`: RC 0. The actual MVS 3.8j job OSEHSTL had DELOLD=0000 and GONE=0000; STAGE, RECV and CLEANUP each had both IEF202I and IEF272I skip messages and no executed-step RC. RECEIVE count stayed 1 before/after the negative job. The driver omits only the target DELETE and changes the job name, retaining the real template/conditions. The original intermittent DELETE cause remains unknown; its consequence is now guarded and tested.
- **R04G-2 closed:** unique guest evidence directories retain failed exports; successful copies are compared by nonempty SHA-256 manifests with LF output before deletion. Host tests exercised failed/incomplete copies and successful two-file export. Additional independent mock cases for failed log capture, failed guest hashing and wrong copied bytes each returned RC 1 with no guest-copy deletion. An independent smoke-wrapper mock returned RC 1 for copy RC 23. No real guest/Docker operation occurs in these mocks. All fixtures and outputs are retained.

Validation (commands run in this review worktree; `OSE_BASH=C:/Program Files/Git/bin/bash.exe`, host `PYTHON=python`):

| Command/check | RC | Evidence/result |
|---|---|---|
| `python -I -m unittest discover -s tests/host -v` | 0 | 68 total: 59 passed, 9 skipped because pinned Sysgen/MVP source caches absent; `artifacts/evidence/review-ose-004-r2/host-tests.txt` |
| `python -I scripts/check_repo.py`; `git diff --check` | 0, 0 | structural/docs checks |
| `DASD_VOLUME=ose-review-004-r2-20261127 sh scripts/deploy.sh stale` | 0 | negative behavior above, clean shutdown, export verified (4 files); `guest/runs/20261127T140242Z-357/deploy-stale/` under `artifacts/evidence/ose-004/` |
| Same environment, `sh scripts/deploy.sh all` | 0 | deploy: GONE=0004 and all other steps=0000; independent LISTDS lists HELLO. Batch RC0=0000 / RC4=0004, exact output. TSO plain CALL7 output and logoff pass. Export verified (4 deploy, 10 run files); `guest/runs/20261127T140408Z-880/` |
| Same environment, `sh scripts/smoke.sh ipl1` | 0 | IPL 8s, ordered clean shutdown, Hercules RC0, no forced quit; `artifacts/evidence/ose-003/smoke-runs/20261127T140740Z-1586/` |
| `python artifacts/evidence/review-ose-004-r2/export-extra.py`; `bash artifacts/evidence/review-ose-004-r2/smoke-export-failure.sh` | 0, 0 | assertions of expected failure behavior passed; mocked wrapper return codes recorded separately |
| `python artifacts/evidence/review-ose-004-r2/audit.py` | 0 | independently asserts the three guest result files and exact negative skip messages |
| Python hash verification | 0 | author rework manifest 26/26 match, SHA256 89858afb8ea23756663b0b3c5dd416e1dba2746c0e0bbb5bf1383d88b523fd94; previous reviewer manifest 32/32 unchanged, SHA256 1ce2cc9214136e98115346692d5c0f7ec859ad51eae532c4c5c3559bc25aa504 |
| Read-only credential/cleanup audit in pinned tools image | 0 | no guest password in review/HELLO evidence; zero deployment result copies left in the volume after verified exports |

Wrapper logs/RCs, fixtures and audits are under `artifacts/evidence/review-ose-004-r2/`. A manual lease covered clone and all guest work on disposable `ose-review-004-r2-20261127`, copied from the stopped independent reviewer baseline `ose-sysgen-review-003-20261127`. Author volumes never mounted. Four cold IPLs (11s, 10s, 8s, 8s), all followed by ordered shutdown messages after the shutdown request, Hercules RC0 and no forced quit. No active containers; lease released; reviewer volume retained stopped. Only review/status/usage documents changed.

Scope: host toolchain build was not repeated; accepted host build and full artifact hashes remain the prior evidence, and its independently built XMIT was verified before reuse. No new full sysgen, UFSD/security/runtime probe suite or package release was attempted. T-8's limited HELLO runtime observations remain appropriate. The OSE-003 evidence overwrite incident is not reversed by this fix; prior independent evidence remains intact. Next action: human integration of the verified guest work.

Re-review evidence manifest: `artifacts/evidence/review-ose-004-r2/REVIEW-SHA256SUMS`, 45 files; SHA-256 `578f97d181ed82cbf87fb8390fba75d0aca211ebfb6ecd182a3cf6c27381192c`.

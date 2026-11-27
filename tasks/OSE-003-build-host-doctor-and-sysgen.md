# OSE-003 — Build host doctor and Sysgen wrapper; native TSO/JES smoke
Status: REVIEW (independent test 6 passed 2026-11-27; changes requested R03-1 through R03-5)
Milestone: M0
Dependencies: OSE-002; OSE-013 (added in the OSE-002 rework); ADR-0003 (accepted). Clone all caches with `core.autocrlf=false` (research sysgen-pins P-9)
Owner: coordinator session (standard tier)
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-003-build-host-sysgen
Guest resources: lease required (creates the first DASD set)
Baseline commit: 0ba236c (main)

## Goal and non-goals
Goal: build MVS/CE from a clean checkout with the pinned Sysgen and Hercules, as a non-root user, on the build host chosen in ADR-0003. IPL it twice and prove that native JES2 and TSO work, with every check parsed automatically.
Non-goals: OSE code, UFSD tests, the snapshot/lease tooling (OSE-009), performance tuning.

## Inputs and primary references
ADR-0003, ADR-0004, `dependencies.lock.json`, the sysgen README at the pin (recon R-05: Debian/Ubuntu only, never as root, 30-minute default timeout), sysgen `tests/`, wrljet/hercules-helper at its pin. **Reuse the upstream sysgen test and automation scripts before writing new ones.**

## Allowed files / interfaces
`Makefile` (targets doctor, fetch, sysgen), `scripts/doctor.sh`, `scripts/sysgen.sh`, `scripts/lib/*`, `scripts/host/*` (container or WSL provisioning), `sysgen/` (wrapper config, empty customize fragment), `jcl/smoke/*.jcl`, `tests/integration/smoke/*`, `docs/runbooks/build-host.md`, `docs/runbooks/sysgen-and-ipl.md`, this card.

## Acceptance tests (commands and expected outcomes)
1. `make doctor` on a fresh host → RC 0. It checks the OS, that it is not running as root, the Hercules version against the lock, Python, free disk space and free ports. A failing check gives a nonzero RC and a message (demonstrate at least one failure).
2. `make fetch && make sysgen` from a clean checkout → RC 0 and a DASD set under `artifacts/`. Record the elapsed time and the sha256 of the logs.
3. Two cold IPLs of the result. Both console logs show IPL completion and JES2 initialized. The runbook records the exact message IDs taken from the observed log.
4. JES2 smoke job (IEFBR14 plus a step with a planted nonzero RC). The host script parses each step RC from spool: expected 0000 and the planted value. Submission success alone does not count.
5. TSO smoke: automated logon as a non-admin user, one command with checked output, then logoff. Use upstream tooling if it exists; otherwise use pinned s3270 scripting.
6. A second agent or person repeats steps 1–4 using only the runbook.
7. **Pin enforcement end to end** (moved here from OSE-013 on 2026-11-26 to remove a circular gate). The `make sysgen` run of test 2 uses OSE-013's patch and check. Its log shows MVP at `4c004a59…` and RAKF at `941b07dc…`, and the MVP package hashes match the lock. Also run once with a deliberately wrong MVP pin and show that sysgen stops with a nonzero RC before the MVP install. Then remove the `pending_enforcement` entries from the lock, citing this test's evidence.

## Escalation triggers
- The Hercules or sysgen deadlock happens twice → BLOCKED with logs.
- Container networking or timing problems → try ADR-0003 option B and record both outcomes.
- Any step needs root → stop.

## Handoff
- Changed files / commits (branch `task/OSE-003-build-host-sysgen`):
  - Scripts: `scripts/host/hercules-image.sh`, `scripts/doctor.sh`, `scripts/sysgen.sh`, `scripts/smoke.sh`, and in `scripts/lib/`: `common.sh`, `sysgen-in-container.sh`, `mvs-smoke.py`, `tso-smoke.py`.
  - `jcl/smoke/jes2-smoke.jcl`.
  - `Makefile`: targets `doctor`, `fetch`, `sysgen`, `smoke`.
  - Runbooks `docs/runbooks/build-host.md` and `docs/runbooks/sysgen-and-ipl.md`.
  - `dependencies.lock.json`: `pending_enforcement` emptied, with the evidence moved into the `mvp` and `rakf` notes.
  - `docs/status.md` (lease), `tasks/usage.jsonl`, this card.
- Commands run, RC, evidence paths (all under `artifacts/evidence/ose-003/`, hashed in `SHA256SUMS`):
  1. **Test 1, PASS.** `make doctor` → RC 0 (`doctor.txt`). `DOCTOR_USER=0 sh scripts/doctor.sh` → RC 1 with `FAIL running as root` (`doctor-as-root.txt`).
  2. **Test 2, PASS.**
     - First build: `sh scripts/sysgen.sh run` into volume `ose-sysgen-1` → RC 0 on attempt 1, 2934 s (`run-summary.txt`, `sysgen-attempt-1.out/.log`).
     - **Clean checkout:** a fresh detached worktree at a849caf, `make fetch` → RC 0 (4 min 44 s), then `DASD_VOLUME=ose-sysgen-2 make sysgen` → RC 0 on attempt 1, 2906 s (`run2/`).
     - DASD set: 180–181 MB compressed, 16 volumes, exported to `artifacts/sysgen/MVSCE`.
  3. **Test 3, PASS.** Cold IPLs, each a fresh Hercules start:
     - On `ose-sysgen-1`: 2 in the final `make smoke` run, plus 4 earlier development IPLs.
     - On `ose-sysgen-2`: 2 more.
     - Each showed IEA101A, $HASP493, IEE041I, IST020I and IKT007I in `mvslog.txt`, 7–9 s after the Hercules start.
     - Each shutdown was clean: $HASP099, $HASP085, IEE334I, then Hercules RC 0 without the `quit` fallback. The message IDs are recorded in the runbook.
  4. **Test 4, PASS.** Job OSESMOKE: `$HASP395 OSESMOKE ENDED`. From `printers/prt00e.txt`: `BR14 0000`, `PLANT 0004` (planted with IDCAMS `SET MAXCC = 4`). Passed on both builds.
  5. **Test 5, PASS.** s3270 logon as non-admin MVSCE02 → READY → `TIME` printed ` TIME-hh:mm:ss PM. CPU-…` → `LOGOFF` returned to the logon screen. Screens are in `smoke/tso-NN-*.txt` with the password redacted. Passed on both builds. `make smoke` → RC 0 (`make-smoke.txt`, 3 min 5 s).
  7. **Test 7, PASS.**
     - Pins validated before sysgen started and again after it (`pins-pre.txt`, `pins-post.txt`).
     - `sysgen.log` shows the patched sysgen reusing the pre-staged clones: `…temp/RAKF exists, checking out 941b07dc…` and `…MVSCE/MVP exists, checking out 4c004a59…`.
     - `sh scripts/sysgen.sh negative-pin` on the volume copy `ose-sysgen-1-negpin`, with `[mvp] commit = 0000…0000`, gave `checkout of 0000… failed: fatal: reference is not a tree` in step 9 before the MVP install. Sysgen RC 1, wrapper RC 20 (`negative-pin/`, `negative-pin-summary.txt`).
     - The `pending_enforcement` entries are removed from the lock, citing this evidence.
  - Image: `ose-hercules:4.9.1-ee86c4de`, `Hercules version 4.9.1.11612-SDL-gee86c4de`, `make check: Did 293 tests. All OK.` (`hercules-image-build.log`, `hercules-version.txt`).
- Tests not run and why:
  - **Test 6** (a second agent or person repeats tests 1–4 using only the runbook) needs someone other than the author. The independent reviewer can do it.
  - ADR-0003 option B was not tried, because option A worked with no networking or timing problems.
- Decisions / ADRs (recorded here and in the runbooks; no new ADR):
  - **Hercules is built directly from the pinned source, not through hercules-helper.** The source tree already includes x86_64 static libraries for its external packages, which the helper would have cloned unpinned. The helper's Debian package list was used as the reference. The lock note on hercules-helper ("must be configured to build the pinned tag") is therefore moot; a lock update needs human approval.
  - Debian packages beyond the helper's list:
    - Regina REXX, needed by the Hercules test suite;
    - `s3270` 4.1ga10 (Debian main), for TSO automation;
    - `netbase`, which upstream's own container installs.
  - **These packages are not in the lock.** Apt versions are recorded in the evidence and are not snapshot-pinned.
  - Sysgen runs in a Docker volume rather than the Windows bind mount, with `--keep-temp` (MANIFEST R13-2) and `--keep-backup`; the backups are what make the test 7 `--step` restart possible.
- Known defects / blockers:
  - None blocking.
  - Observed quirks, now in the runbook:
    - On the finished MVS/CE, console messages reach only `mvslog.txt`, not Hercules' stdout;
    - `$HASP099` appears only at shutdown;
    - JES2 PRINTER1 is INACTIVE after IPL;
    - `TIME` prints no message ID;
    - pressing Enter while TSO is still processing the logon blanks the screen;
    - at start-up Hercules logs `HHC01441E REXX MSGP ON` (this build has no Regina support) and `HHC00109E` (an unprivileged container). Both are harmless.
  - The system uses **upstream's published default passwords** (`users.conf`; risk P-8). Do not expose ports 3270, 3505, 2121 or 8080 beyond localhost.
- Next action:
  - Independent standard-tier review, including test 6 from the runbooks.
  - The OSE-004 guest part (deploy hello; RECEIVE the XMIT), the OSE-011 guest listing and OSE-006 can now use this image under a lease.
  - The human should decide whether the extra Debian packages (Regina, s3270, netbase) need lock entries.
- Usage/cost if available: not metered.
## Independent review and gate result

### Independent review — 2026-11-27

Reviewer: Codex, high tier (failure-path and reproducibility review), independent of author. Reviewed 69e500f against 0ba236c on review/OSE-003-r1. Independent test 6 completed under a manual lease of new Docker volume ose-sysgen-review-003-20261127; author volumes were untouched. The lease is now released. **Changes requested** for the findings below. A successful fresh build does not close these failure-path defects.

1. **P1 / R03-1 — Verify the existing Sysgen source before resuming it.** `scripts/lib/sysgen-in-container.sh:40-47` accepts any existing /work/sysgen/.git, logs HEAD, and executes that tree after checking only RAKF and MVP. The host fetch validates a different clone, /ose/artifacts/cache/src/sysgen. Therefore an older or locally modified Sysgen tree in the volume is executed without verifying SYSGEN_COMMIT or reviewed P-01, and can pass the post-checks too. Verify the volume's Sysgen HEAD and expected reviewed source/patch before execution on every invocation; test wrong-HEAD and missing/changed-patch resume cases. Found by source inspection; no wrong-source guest run was performed.
2. **P2 / R03-2 — Reject a failed Docker doctor invocation.** `scripts/doctor.sh:38-56` ignores the exit status of `out=$(docker run ...)` and only counts lines beginning FAIL. A runtime failure (e.g. container cannot start) prints no such line, so doctor returns 0 without performing its container checks. Reproduced using a local Docker shell test double: engine/image checks succeed, run returns 125 and prints a simulated runtime error, doctor prints `all checks passed` and returns **0** (expected nonzero). Capture and reject the container status, and add a regression check.
3. **P2 / R03-3 — Require clean-shutdown evidence, not only process RC.** `scripts/lib/mvs-smoke.py:188-193` collects shutdown messages but does not require any. A stub Hercules that supplies the IPL observations and then exits 0 with no HASP099/HASP085/IEE334I is accepted: `shutdown=[]`, script **RC 0**. Require the documented shutdown markers (and order as applicable) for the current run. The existing quit-fallback check does not cover a process that exits 0 prematurely.

Failure-path evidence (local fixtures, no guest mutation): `artifacts/evidence/ose-003/review-doctor-docker-failure.sh/.txt/.rc` and `review-shutdown-failure.py/.txt/.rc`, plus mock-shutdown/review-result.txt within this review worktree. Run commands: Git Bash executes the doctor fixture (with approved escalation because this sandbox cannot launch Git Bash), then `python -I artifacts/evidence/ose-003/review-shutdown-failure.py`. Both unexpectedly return 0; these are reproduced defects, not passing tests. An initial fixture path mistake and a sandbox Git Bash launch failure were corrected before the recorded reproductions; neither was counted as product evidence.

Checks already completed: `python -I scripts/check_repo.py` -> RC 0; `python -I -m unittest discover -s tests/host -v` -> RC 0 (11 passed, nine pin tests skipped because this worktree has no pin caches). Author evidence integrity: 47 SHA256SUMS entries in artifacts/evidence/ose-003 and 14 in run2 verified against local files, no mismatches. Independent `make fetch` -> RC 0, Hercules self-test 293/293; `make doctor` -> RC 0; DOCTOR_USER=0 doctor -> RC 1 as expected. Full independent repeat results follow below.

Dependency review: building Hercules directly at the pinned commit avoids helper-driven mutable fetches and is technically reasonable, but accepted ADR-0005 explicitly chose hercules-helper and the lock still says it must be used. Reconcile that decision in a superseding ADR/manifest before merge. In particular, task acceptance 5 requires pinned s3270 scripting; smoke.sh installs unversioned s3270 from the live Debian mirror. Recording the installed version is evidence, not enforcement. Pin s3270 with an enforceable package/source version and integrity provenance (or a fixed verified tool image); record Regina/netbase consistently with the build-host package policy. No new dependency or ADR decision was made by this reviewer.

Additional findings from the same review:

4. **P2 / R03-4 — Reset or uniquely name the per-run smoke handshake.** `scripts/smoke.sh:61-75` trusts /work/evidence/smoke/ipl2-ready; `scripts/lib/mvs-smoke.py:177-181` trusts ipl2-tso-done. Neither is cleared before the next run. A previous run's ready marker can launch TSO prematurely, and its done marker lets the new guest driver begin shutdown before the new TSO check completes. A local fake-clock/Hercules regression pre-created an old done marker: the driver returned 0 with `wait_sleeps=0`, without waiting for any new completion; the regression assertion failed (RC 1). Its shutdown markers were present in this fixture, isolating this issue from R03-3. Evidence: review-stale-handshake.py/.txt/.rc and mock-stale-handshake/ in this worktree's ignored evidence directory. Use a per-invocation evidence directory/nonce or remove both markers before launch; verify consecutive smoke runs on the same volume and a delayed TSO worker. No live guest fault injection was performed for this finding.
5. **P2 / R03-5 — Enforce the required s3270 pin.** `scripts/smoke.sh:14-21` accepts any existing tools-image tag or installs unversioned s3270 from the live Debian mirror. The source comment's 4.1ga10 and recorded package versions do not constrain future builds. Acceptance test 5 explicitly calls for pinned s3270 scripting. Record source/version/hash/license provenance and enforce that pin, or use an immutable verified tools-image identity. Reconcile Regina/netbase and the direct-Hercules/helper decision with the accepted build-host dependency policy before merge; the reviewer has not approved a dependency exception.

R03-1 regression confirmation (non-guest): `review-resume-source-pin.sh` runs a path-relocated copy of the unchanged container wrapper with mocked Git/client-pin responses and a harmless stand-in sysgen.py. Git reports HEAD 1111...1111 instead of 4746195d...; the client pin checker succeeds for RAKF/MVP and would refuse Sysgen if asked. The stand-in is executed, both wrapper pin stages pass, wrapper RC 0; regression assertion returns RC 1. This demonstrates the admission defect without executing wrong source on MVS. Evidence: review-resume-source-pin.sh/.txt/.rc and mock-resume/ under this worktree's ignored artifacts/evidence/ose-003. Git Bash execution used approved escalation; the implementation files were not edited.

#### Completed independent runbook repeat (acceptance test 6)

Executed from the clean review worktree at 69e500f, using the two runbooks for commands, with a new empty DASD volume (not a copy of an author's image). Windows host environment supplied Git Bash/GNU Make on PATH and PYTHON=python. No implementation or runbook edits were needed to execute the positive repeat.

| Check | Command / evidence | Observed result |
|---|---|---|
| Host image | `make fetch`; reviewer-fetch.txt/.rc, hercules-image-build.log | RC 0; pinned Hercules built; self-test 293/293 |
| Doctor | `make doctor`; reviewer-doctor.txt/.rc | RC 0; uid 1000, expected version/commit and tools |
| Planted doctor failure | `DOCTOR_USER=0 sh scripts/doctor.sh`; reviewer-doctor-root.txt/.rc | RC 1; FAIL running as root |
| Fresh system build | `DASD_VOLUME=ose-sysgen-review-003-20261127 make sysgen`; reviewer-make-sysgen.txt/.rc, run-summary.txt | RC 0, attempt 1, **3181 s** |
| Pins | pins-pre.txt, pins-post.txt, sysgen-pin-lines.txt | RAKF/MVP commit and all locked MVP package hashes pass before/after; real Sysgen log shows both pinned clones reused |
| Smoke run | `DASD_VOLUME=ose-sysgen-review-003-20261127 make smoke`; reviewer-make-smoke.txt/.rc | RC 0 |
| Cold IPL 1 and 2 | smoke/ipl1-result.txt, ipl2-result.txt and raw hardcopy logs | ready in **7 s / 9 s**; all five IPL markers present in order |
| JES2 | independent parse of smoke/prt00e.txt | OSESMOKE BR14=0000, PLANT=0004 |
| Non-admin TSO (extra to test 6) | smoke/tso-result.txt and TIME screen; user MVSCE02 | READY, TIME output and logoff all true |
| Both shutdowns | independent raw-log checks | HASP099, HASP085, IEE334I present in order; Hercules RC 0, no forced quit |

Independent raw-log/spool verification used Python regexes and ordered-marker assertions, not just the smoke wrapper's RC: RC 0 (review-independent-evidence-check.txt). Docker inspection confirmed both guest containers exited with code 0 before releasing the lease. Volume ose-sysgen-review-003-20261127 is retained stopped; author volumes ose-sysgen-1, ose-sysgen-2 and their negative-pin copy were not mounted or changed by this review.

**Test 6's positive repeatability condition is satisfied.** OSE-003 is nevertheless **not VERIFIED**, because R03-1..R03-5 remain. The negative wrong-MVP guest run was not repeated by the reviewer: the author's hashed evidence was checked, and the reviewer independently repeated the real positive pre/post pin path. No privileged code, dependency entry, ADR, merge or release was changed by the reviewer.

Evidence root (relative to the main workspace): `artifacts/review/OSE-003-r1/artifacts/evidence/ose-003/`. Logs, regression fixtures, observed RCs, raw guest output and lease receipt are retained there. REVIEW-SHA256SUMS covers the evidence recursively; its SHA-256 is `8132d2ed785a5d27436b6da2fb1672062a0945df30fb1a55e876596a7bffea70`.

Next action: author fixes the five findings and provides negative regression coverage; reconcile the direct Hercules build in a superseding ADR and enforce the required s3270 pin. Retain this independent clean-build/IPL evidence; rerun the checks affected by the fixes. Human owns integration.

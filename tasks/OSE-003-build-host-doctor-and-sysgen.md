# OSE-003 — Build host doctor and Sysgen wrapper; native TSO/JES smoke
Status: IMPLEMENTED (2026-11-26/27; tests 1-5 and 7 passed, test 6 needs a second agent or person; awaiting independent standard-tier review)
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

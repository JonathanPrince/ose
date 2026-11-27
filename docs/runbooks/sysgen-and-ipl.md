# Runbook: pinned sysgen, IPL, JES2 and TSO smoke (OSE-003)

Last verified: 2026-11-26, branch `task/OSE-003-build-host-sysgen`, on the build host from [build-host.md](build-host.md). **Before you start, hold the guest lease:** your task ID must be on the `Guest lease:` line of `docs/status.md` (tasks/README.md, "Guest resources").

## Prerequisites
- `make doctor` passes.
- About 6 GB free for the Docker volume, which keeps the sysgen backups.
- Network access to GitHub (sysgen, RAKF, MVP, and the pinned mvslovers release assets).

## 1. Sysgen: `make sysgen` (= `sh scripts/sysgen.sh run`)
The run takes place in the Docker volume `ose-sysgen-1` (override with `DASD_VOLUME=`), not on the bind mount. It follows `upstream/sysgen/MANIFEST.md` steps 1–3b:
- check out sysgen `4746195d` with LF line endings and apply patch P-01;
- **step 1b, on every run, including a resume of an existing volume:** the tree must be exactly the pin plus P-01. HEAD must be `4746195d`, and the tracked files must hash to the same git tree as the pin with P-01 applied. Untracked build products (`temp/`, `MVSCE/`, logs) are not compared; the RAKF and MVP clones among them are checked next. If anything differs, the run stops with RC 10 before any upstream code runs, and the differing paths are listed in `wrapper.log`;
- pre-stage RAKF at `941b07dc` and MVP at `4c004a59` at the paths sysgen uses;
- validate them with `pins.py` **before** sysgen starts;
- run `./sysgen.py --keep-temp --keep-backup --timeout 3600 --version ose-003 --CONTINUE`, with up to `ATTEMPTS=3` tries;
- re-validate the pins afterwards;
- export `MVSCE/` to `artifacts/sysgen/MVSCE` and the logs to `artifacts/evidence/ose-003/`.

| Outcome | RC | Meaning |
|---|---|---|
| success | 0 | `run-summary.txt: sysgen run rc=0 elapsed=…` |
| 10 | source or pin validation failed | sysgen was **not** started; see `wrapper.log` (step 1b: sysgen tree) or `pins-pre.txt` (step 3: RAKF, MVP). A refused volume is not repaired: start again in a new volume |
| 20 | sysgen failed `ATTEMPTS` times | see `sysgen-attempt-N.out` and `.log`; run it again (it continues from `.step`). A second hang counts as an escalation: the card goes BLOCKED |
| 30 | post-run pin check failed | the build is invalid; see `pins-post.txt` |

Observed 2026-11-26: **RC 0 on attempt 1, 2934 s (49 min)**. The result is 180 MB of compressed DASD: `mvsres` `mvs000` `page00` `spool1` `smp000` `work00` `work01` `syscpk` (3350), `pub000` (3380), `pub001` (3390) and `sortw1`–`sortw6` (2314). Log hashes are in `artifacts/evidence/ose-003/SHA256SUMS`.

Progress during a run: `sh scripts/sysgen.sh status`. Steps 1–14 print `[+] … Step N.` lines in `sysgen-attempt-1.out`. On this host, step 4 started at +11 min, step 9 (MVP) at +40 min and step 14 at +48 min.

## 2. IPL and smoke: `make smoke` (= `sh scripts/smoke.sh all`)
Two cold IPLs of the built system, each a fresh Hercules start running `hercules -f conf/local.cnf -r conf/mvsce.rc`:
- **IPL 1:** IPL, then a clean shutdown.
- **IPL 2:** IPL, the JES2 job, the TSO session, then a clean shutdown.

**Where to look.** On the finished MVS/CE, console messages do **not** appear on Hercules' stdout. They go to the master console and its hardcopy printer `0015 = MVSCE/mvslog.txt`. The build-time marker `$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE` does not appear at IPL; it appears only during shutdown.

**IPL complete**, as observed in `mvslog.txt` on every IPL on 2026-11-26, in this order, about 8 s after Hercules starts:

| Message | Text |
|---|---|
| `IEA101A` | `SPECIFY SYSTEM PARAMETERS FOR RELEASE 03.8 .VS2` (NIP; answered by the `hao` rules in `conf/mvsce.rc`) |
| `$HASP493` | `JES2  QUICK-START IS IN PROGRESS` (one IPL showed `WARM-START`; both are accepted) |
| `IEE041I` | `THE SYSTEM LOG IS NOW ACTIVE` |
| `IST020I` | `VTAM INITIALIZATION COMPLETE` |
| `IKT007I` | `TCAS ACCEPTING LOGONS` (TSO is ready) |

Expected noise, which is not an error:
- `IEA000I nnn,IOE,05,0200,…,NET` for every 3270 terminal at 400–41F that has no client connected;
- `IST025I BLDL FAILED FOR IEDIAE/IEDIAK IN VTAMLIB`;
- `HHC00109E set_thread_priority … Operation not permitted`, because the container is not privileged.

**JES2 smoke** (`jcl/smoke/jes2-smoke.jcl`). The driver issues `$S PRT1` first: PRINTER1, class A on `00E`, is `INACTIVE` after IPL. It then submits the job to the card-reader socket `127.0.0.1:3505`, waits for `$HASP395 OSESMOKE ENDED` in the hardcopy, and parses `IEF142I OSESMOKE <step> - STEP WAS EXECUTED - COND CODE nnnn` from `printers/prt00e.txt`. Expected and observed: `BR14 0000` and `PLANT 0004`. The planted RC comes from IDCAMS `SET MAXCC = 4`.

**TSO smoke** (`scripts/lib/tso-smoke.py`, with s3270 on `127.0.0.1:3270`), as user **MVSCE02**. That is a non-admin user (NOOPER, NOADMIN) from upstream's `users.conf`. Its password is upstream's published default and is read from the volume at run time, never stored in this repository.

| Screen | Action |
|---|---|
| Hercules 3270 logo, `CLEAR the screen or hit ENTER` | Enter |
| VTAM `TSO Logon ===>` | `LOGON MVSCE02/<password>` |
| MVS/CE welcome banner ending in `READY` | `TIME` |
| ` TIME-hh:mm:ss PM. CPU-… SERVICE-… SESSION-… <date>` (MVS 3.8j prints **no** message ID here) | `LOGOFF` |
| the terminal returns to the logo or the logon screen | done |

Do not press Enter while TSO is still processing the logon. On 2026-11-26 that blanked the screen.

**Clean shutdown**: Hercules command `script SCRIPTS/SHUTDOWN.RC` (upstream). Observed sequence:
1. `$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE`
2. `$HASP085 JES2 TERMINATION COMPLETE`
3. `IEE334I HALT     EOD SUCCESSFUL`
4. Hercules exits with RC 0.

The smoke requires all three messages, **in this order and after its own shutdown request** (R03-3). It fails if any is missing, if Hercules had already exited before the request, if Hercules' RC is not 0, or if the `quit` fallback was needed. `ipl*-result.txt` records `shutdown_messages`, `shutdown_missing` and `exited_before_shutdown`.

**TSO handshake** (R03-4): in IPL 2, `mvs-smoke.py` (in the container) and `smoke.sh` (on the host) coordinate through two files, `ipl2-<run-id>-ready` and `ipl2-<run-id>-tso-done`. The run ID is new for every `smoke.sh` invocation, and `mvs-smoke.py` deletes every older `ipl2-*` marker before Hercules starts. A previous run's files can therefore neither start TSO early nor end the IPL before this run's TSO check. If no `tso-done` arrives within 900 s, IPL 2 fails.

Evidence: a new directory per invocation, `artifacts/evidence/ose-003/smoke-runs/<UTC>-<pid>/`, which must not exist yet. The volume's own `/work/evidence/smoke/` is emptied at the start, so nothing from an earlier run is exported as this run's. (Before 2026-11-27 the export went to the fixed `artifacts/evidence/ose-003/smoke/`; see the incident note there.) It holds:
- `ipl1-*` and `ipl2-*`: `hercules.log`, `mvslog.txt` and `result.txt`;
- `prt00e.txt`;
- `tso-NN-*.txt` (the screens, password redacted) and `tso-s3270.log`.

Observed 2026-11-26: `make smoke` gave RC 0 in 3 min 5 s.

## 3. Negative pin test: `sh scripts/sysgen.sh negative-pin`
This runs on a **copy** of the volume (`ose-sysgen-1-negpin`), because a `--step` restart restores step-8 DASD. It sets `[mvp] commit` in `mvslovers.conf` to `0000…0000` and runs `./sysgen.py --step step_09_mvp` once. Expected: a nonzero RC before the MVP install. Evidence is in `artifacts/evidence/ose-003/negative-pin/`. The result is recorded in the OSE-003 card.

## 4. Ending the lease
Delete the volume copies when they are no longer needed, with `docker volume rm ose-sysgen-1-negpin`. Keep `ose-sysgen-1` until OSE-009 defines snapshots. Then clear the `Guest lease:` line in `docs/status.md`.

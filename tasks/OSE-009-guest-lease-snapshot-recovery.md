# OSE-009 — Guest lease, snapshot and recovery harness
Status: MERGED (VERIFIED at 6f13967, independent re-review 2026-11-27; merged to main 2026-11-27 on the human maintainer's instruction; the tool lease protocol is now in force)
Milestone: M0a (generic platform)
Dependencies: OSE-003
Owner: coordinator session (standard tier)
Risk: medium
Model tier: standard
Reviewer tier: standard
Budget: local-only
Branch: task/OSE-009-guest-harness
Guest resources: creates its own disposable images
Baseline commit: 730757f (main)

## Goal and non-goals
Goal: tooling that (a) gives each task an isolated guest image with configurable ports, (b) makes it impossible for two mutating tasks to use the same emulator or DASD set at once, and (c) snapshots and restores a known-good DASD set. It must be proven by forced-failure recovery. This replaces the manual `Guest lease:` line in `docs/status.md`.
The harness must use package-neutral guest/volume/port configuration and be usable by both the MVP example projects and OSE, without an OSE runtime service. It is the next implementation priority and feeds OSE-014; no OSE-006/007/008 completion is required.
Non-goals: a general orchestrator (spec §10), cloud hosting.

## Inputs and primary references
OSE-003 runbooks and scripts; Hercules documentation at the pinned version (shadow files, config, ports); spec §4 and §6.

## Allowed files / interfaces
`Makefile` (restore, a lease helper), `scripts/guest/*`, `tests/integration/harness/*`, `docs/runbooks/guest-lease-snapshot-restore.md`, `tasks/README.md` (the guest-resources section, edited only after review), this card.

## Acceptance tests (commands and expected outcomes)
1. Acquiring a lease on a DASD set succeeds. A second acquire on the same set exits nonzero with the holder's identity, and a stale lease (dead holder PID) is detected and reported, not silently stolen.
2. Two images with different ports run at the same time without conflict.
3. Snapshot, IPL, modify the guest, forced kill of Hercules (`kill -9`), restore, IPL → the OSE-003 JES/TSO smoke passes and the modification is gone.
4. A snapshot's sha256 manifest is verified on restore, and a corrupted snapshot is refused.
5. Every command exits nonzero on failure, and logs go to `artifacts/`.

## Escalation triggers
Hercules locking or shadow-file behavior differs from its documentation → record it, and fall back to full copies.

## Handoff
- Changed files / commits (branch `task/OSE-009-guest-harness` from main 730757f):
  - New: `scripts/guest/guest.py` (leases, snapshots, restore), `tests/integration/harness/recovery.sh` (acceptance 2-4 end to end), `tests/integration/harness/marker.py` (package-neutral guest modification), `tests/host/test_guest_harness.py` (19 tests), `docs/runbooks/guest-lease-snapshot-restore.md`.
  - Changed: `scripts/lib/common.sh` (`guest_lease_begin`/`guest_lease_end`, `holder_pid`, `guest_container`, `guest_ports`; `guest_run` uses per-volume names and the optional port); `scripts/smoke.sh`, `scripts/deploy.sh`, `scripts/audit-listing.sh` and `scripts/sysgen.sh` (run, negative-pin) take the lease and name containers per volume; `Makefile` (`restore`, `lease-status`); `tests/host/test_hello_guest.py` (the deploy fake-docker tests keep their lease in their own temp directory).
  - Outside the card's list: the guest scripts, `common.sh` and the OSE-004 test file. Leases have to be enforced where guests are started, so these could not stay untouched; the reviewer should check them.
- Commands run, RC, evidence paths:
  - `python -m unittest tests.host.test_guest_harness` → RC 0 (19 tests). They cover: a second acquire names the holder; a stale lease is reported and its file left untouched, `break` works only when stale and refuses a live lease; release and check need the token; a holder that died is reported; leases are per volume; a running container blocks acquire; a concurrent create loses cleanly; snapshot verify refuses a corrupted tar or manifest; restore refuses a corrupted snapshot **before any docker call**, refuses without the lease and refuses a running guest; every command logs. Shell-level: a real `smoke.sh` on a volume leased by another live holder exits nonzero, names the holder, and starts no container.
  - `python -m unittest discover -s tests/host` → RC 0 (109 tests); `python -I scripts/check_repo.py` → RC 0.
  - **Guest, end to end:** `sh tests/integration/harness/recovery.sh` → **RC 0, 0 failures** (`artifacts/evidence/ose-009/runs/20261127T155635Z-1321/summary.txt`; `SHA256SUMS` there has 31 entries, its own SHA-256 `70fcc1551c8f58696d19d932885709e601059fbc47c68c1167a16724aa6c9429`). Baseline snapshot of `ose-sysgen-1` (read only), restored into the new volumes `ose-h009-a` and `ose-h009-b`.

| Acceptance | Result lines from summary.txt |
|---|---|
| 1 leases | host tests above; during the run `lease status` showed all three leases ALIVE under the orchestrator PID, and `no leases` afterwards |
| 2 two images, different ports, same time | 2a/2b: both JES2/TSO smokes RC 0, run concurrently; 2c: both containers up at once and both TN3270 ports (127.0.0.1:13270, :13271) answered with data |
| 3 snapshot, IPL, modify, kill -9, restore, IPL | 3a: marker data set created and LISTCATed while the guest ran; 3b-3d: `kill -9` to the Hercules PID, the driver saw it die with rc -9; 3e: the marker **survived** the kill (check before restore); 3f-3g: restore RC 0 and the volume content changed; 3h: JES2/TSO smoke on the restored guest RC 0; 3i: marker **gone** |
| 4 manifest verified, corruption refused | 4a/4b: verify and restore of a copy with one flipped byte → RC 6; 4c: the guest volume's file manifest is identical before and after the refused restore |
| 5 nonzero on failure, logs under artifacts | exit codes 1-7 per failure class (see the tool header); every tool command logs to `artifacts/guest/logs/`; the harness writes `artifacts/evidence/ose-009/runs/` |

- Tests not run and why: the Linux host path (developed and run on Windows/Git Bash only; the code has a POSIX branch for process liveness, unexercised); `sysgen.sh` with the lease (a 50-minute run; the change is the same `guest_lease_begin` call that smoke, deploy and the listing exercised); leases across two hosts (reported as FOREIGN and never broken, untested).
- Decisions / ADRs: no new dependency. Leases are host-wide in `OSE_LEASE_DIR` (default `~/.ose-guest/leases`), not under `artifacts/`, because Docker volumes are host-wide and several worktrees share them. Snapshots are full copies (tar plus manifests), not Hercules shadow files: a guest is only 180 MB, and a full copy needs no CCKD shadow semantics (escalation trigger avoided, not hit).
- Known defects / blockers:
  - First end-to-end run failed at 3b. With `--externalgui`, Hercules' process name is `dyngui`, so `pgrep -x hercules` found nothing. The run then aborted, and its exit trap released the leases while its marker container still ran on `ose-h009-a`, so a guest ran without a lease for about a minute until removed by hand. Both fixed: the kill matches the command line, and the trap removes its own containers before releasing.
  - The lease is advisory. Every script in this repository takes it, and `lease acquire` refuses a volume with a running container, but `docker run` by hand bypasses it.
  - PID reuse after a holder dies could make a stale lease look alive (it would then be reported as held, the safe direction).
- Next action: independent review; after it, the `Guest lease:` line in `docs/status.md` and tasks/README.md "Guest resources" can point to `make lease-status` (README edit only after review, per this card); then OSE-014.
- Usage/cost if available: not metered.
## Independent review and gate result

### Scheduling amendment — 2026-11-27
Human direction: deliver the generic platform before new OSE-specific work. OSE-003 is merged, so this card is READY. Implement and independently review isolation/recovery first, then use it for OSE-014. Acceptance tests above remain mandatory; existing manual leases remain in force until the replacement is reviewed. No harness acceptance test ran as part of this documentation amendment.

### Independent review — 2026-11-27

Reviewer: Codex, independent of author; high-tier safety review after reproducing destructive restore/lease failure paths. Reviewed `dc83bd5` against `730757f` on `review/OSE-009-r1`, separate worktree `artifacts/review/OSE-009-r1`. **Changes requested: R09-1 through R09-6.** The complete positive end-to-end recovery run independently passed; failure-path defects prevent VERIFIED. Keep the manual `Guest lease:` protocol and tasks/README.md guest rules in force. No merge/push or implementation changes.

- **R09-1 [P1], `scripts/sysgen.sh:77` — Lease the negative-pin target independently.** Only the source is leased. The derived <source>-negpin volume is removed, populated and started without checking its lease. A fake-backend run with that target already leased to OTHER-REVIEW-HOLDER still requests its removal and starts the copied sysgen. Reassigning DASD_VOLUME also makes the exit trap release the source token against the target; it fails and leaves the source lease behind while the command returns 0. Acquire/check both volumes, retain their original identities for cleanup, and derive the container name for the target. No full sysgen is needed to test this path. Proof under reviewer evidence: `shell-faults.py, shell-faults.json, shell-faults/negative-pin/output.txt`.

- **R09-2 [P1], `scripts/guest/guest.py:357` — Roll back both guest and user configuration after a late restore failure.** The restore commits MVSCE before replacing users.conf; failure of the latter returns 7 without rolling back the guest. The unchanged RESTORE_SH run in the pinned Docker image against tiny disposable bind-mounted files, with users.conf.new made a directory, returned 7 and left NEW_GUEST plus OLD_USERS, retaining MVSCE.previous only in scratch. This contradicts the advertised unchanged-volume/previous-guest guarantee. Stage both replacements and restore the original pair on every post-swap failure; report rollback failure truthfully. Proof under reviewer evidence: `restore-fault.rc, restore-fault.txt, restore-fault/restore.sh, restore-fault/work/`.

- **R09-3 [P1], `scripts/guest/guest.py:170` — Fail closed when Docker cannot determine whether a volume is busy.** running_containers uses check=False and treats empty stdout as idle without checking the return code. A Docker ps failure therefore permits lease acquisition and require_stopped. The independent mock returned rc1 with an error; acquisition returned 0 and require_stopped accepted it. Abort before leasing/snapshotting/restoring when the query fails, and add failure-path tests. Proof under reviewer evidence: `admission-faults.py, admission-faults.json`.

- **R09-4 [P2], `scripts/lib/common.sh:106` — Keep leases until owned containers are confirmed stopped.** The shared EXIT trap only releases the token. A real audit-listing.sh invocation with fake Docker wait failing rc17 returned 1 and deleted its lease while the detached fake container stayed running. The recovery test trap likewise tracks only MNAME, not the background smoke containers. Central lease release also permits active containers. Track/stop owned containers and confirm termination before release; on failed cleanup preserve the lease and report recovery needed. Do not forcibly stop somebody else's container. Proof under reviewer evidence: `shell-faults.py, shell-faults.json, shell-faults/wait-fails/output.txt`.

- **R09-5 [P2], `scripts/guest/guest.py:368` — Validate lease ownership before restore --create mutates Docker state.** cmd_restore creates and chowns a volume before require_lease. A valid-hash snapshot fixture and wrong token caused volume create and root chown requests before RC3. Move ownership validation ahead of all mutating Docker calls and assert no create/chown/run on a missing or incorrect lease. This reproduction uses fake Docker only. Proof under reviewer evidence: `admission-faults.py, admission-faults.json`.

- **R09-6 [P2], `tests/host/test_guest_harness.py:24` — Avoid whole-environment patching in guest-harness tests.** mock.patch.dict(os.environ, ...) clears/rebuilds the full environment on exit, reproducing the recently fixed Windows Git config regression. One test_pid_alive test passes but changes same-process git init from RC0 to RC128 (missing GIT_CONFIG_VALUE_0). The complete host suite has 11 ResumeAdmission errors. Set module paths directly after import, or save/restore only the three owned environment keys; retain empty unrelated native environment entries. Proof under reviewer evidence: `environment-repro.py, environment-repro.json, host-tests.txt`.

Validation (paths relative to the review worktree unless explicitly the main workspace):

| Command/check | RC | Result / evidence |
|---|---|---|
| `SRC_VOLUME=ose-sysgen-review-003-20261127 VOL_A=ose-review-009-a-20261127 VOL_B=ose-review-009-b-20261127 PORT_A=14270 PORT_B=14271 PYTHON=python sh tests/integration/harness/recovery.sh` | 0 | full positive repeat: snapshot and restore of the independent reviewer baseline; two simultaneous guests with both TN3270 ports answering, concurrent JES/TSO smokes; marker created, Hercules killed by SIGKILL, marker present before restore, absent afterward; post-restore JES/TSO pass; corrupted snapshot verify/restore RC6 and unchanged-volume hash. `artifacts/evidence/ose-009/runs/20261127T162533Z-18/summary.txt`; wrapper log/RC in reviewer evidence |
| `OSE_BASH=C:/Program Files/Git/bin/bash.exe python -I -m unittest discover -s tests/host -v` | 1 | 109 total: 89 passed, 11 errors, 9 skipped (source caches absent). The 11 errors are unchanged ResumeAdmission fixtures failing git init after new environment-patching tests; `host-tests.txt` and `.rc` |
| `python artifacts/evidence/review-ose-009/admission-faults.py` | 0 | reproduction assertions pass: Docker ps error still admits lease/stopped check; restore --create mutates fake Docker state before rejecting the missing lease; `admission-faults.json`. No real Docker operation in this fixture |
| Pinned `ose-hercules:4.9.1-ee86c4de`, `sh /fixture/restore.sh repro`, user 1000:1000, disposable bind-mounted fixture | 7 (expected reproduction) | exact RESTORE_SH fails at users.conf replacement but leaves NEW_GUEST / OLD_USERS. No guest volume involved; unchanged script, tiny tar, old/new files and stdout/RC retained in `restore-fault*` |
| `python artifacts/evidence/review-ose-009/shell-faults.py` | 0 | real shell entry points against fake Docker/Git, private lease directories: audit wait error releases lease while container remains flagged running; negative-pin mutates a target leased to another holder and retains source lease after wrong-volume release attempt; `shell-faults.json` |
| `python artifacts/evidence/review-ose-009/environment-repro.py` | 0 | one new guest-harness unit test passes; same-process native git init RC0 before / RC128 after (`missing config value GIT_CONFIG_VALUE_0`); JSON/fixture retained |
| Python SHA-256 verification of author's manifest | 0 | 31/31 entries match; manifest SHA256 70fcc1551c8f58696d19d932885709e601059fbc47c68c1167a16724aa6c9429; `author-manifest.json` |
| Read-only credential scan; final `docker ps`; `python -I scripts/guest/guest.py lease status` | 0 | no guest password in evidence; no running containers; no actual host-wide tool leases. Fixture-only lease files remain in ignored evidence and do not govern Docker resources |
| `python -I scripts/check_repo.py`; `git diff --check` | 0, 0 | repository/docs checks |

Evidence root: `artifacts/evidence/review-ose-009/`. The normal recovery run used only new disposable reviewer volumes and the stopped independent reviewer baseline, never author volumes. The script's full snapshot is `artifacts/guest/snapshots/h009-base-20261127t162533z-18/`. A manual review lease covered all real guest work in addition to the tool leases. Both tool and manual leases released after containers stopped; reviewer guests retained stopped. The forced kill was the intended isolated fault test. The extra restore failure used tiny scratch bind-mounted files, not DASD. Fake-backend tests never called real Docker, Git fetch or sysgen.

Scope: the advisory boundary around manual docker run is documented and is not itself a review defect; findings concern the repository's own operations. Full-copy snapshots and shared host-account lease storage are reasonable baseline choices. Scope extensions to guest entry points/common.sh and host regressions are necessary for enforcement. Linux host process/path behavior, cross-machine leases, and a new full 50-minute sysgen were not run. The runbook should label Linux host support unverified rather than asserting it works the same. The negative-pin shell path was exercised with a fake backend and fails the lease contract without needing a long build. New guest/privileged runtime interfaces were not introduced in this review.

Next action: fix the six findings at high tier and add targeted failure regressions, retaining this successful normal recovery evidence. Re-review before replacing the manual protocol or starting OSE-014. Human owns integration.

Independent summary has 15 RESULT checks, all passing.

Reviewer evidence manifest: `artifacts/evidence/review-ose-009/REVIEW-SHA256SUMS`, 156 files; SHA-256 `545af9ac49b34a4de6189a77146dc921d6cb92c121073761df4e3e5bfe12a1ff`.

### Rework after review r1 (R09-1..R09-6), 2026-11-27, author
Baseline: review/OSE-009-r1 at 613f777 (fast-forwarded). The manual `Guest lease:` line was set for the guest runs and released afterwards; the manual protocol stays in force.

| Finding | Fix | Regression evidence |
|---|---|---|
| R09-1 (P1) negative-pin target unleased | `sysgen.sh negative-pin` leases `<source>-negpin` itself before `volume rm`, copy or start. `common.sh` keeps a list of leases, each with its own volume and token, so cleanup no longer depends on `DASD_VOLUME`. The container is named for the target. | `ShellLeases`, real `sysgen.sh negative-pin` with fake docker/git: target leased by OTHER-REVIEW-HOLDER → RC≠0, no `volume rm`, no `run -d`, source lease released, the other lease untouched. Normal path → both leased, `ose-sysgen-run-<target>` started with the target's label, `ps` of the target checked before `volume rm`, both leases released |
| R09-2 (P1) late restore failure left a mixed guest | `RESTORE_SH` saves `users.conf` and stages the new one before `MVSCE` moves. After the swap, any failure restores `MVSCE` and `users.conf` (RC 7). A failed rollback is RC 8, with the old guest kept in `.restore-<pid>/`, mapped to `guest.py` RC 8. `RESTORE_WORK`/`RESTORE_SNAP` allow tests outside the container. | `RestoreScript`: the real script under bash with an `mv` wrapper keyed on source paths. Success replaces both; checksum mismatch and a blocked `users.conf.new` (the reviewer's case) change nothing; a late `users.conf` failure rolls back both to the exact original bytes; a failed rollback returns 8 and keeps the old pair. The same four cases in the pinned image via `tests/integration/harness/restore_faults_in_image.py` → RC 0, all as expected (`rework-r1/restore-faults-in-image.json`) |
| R09-3 (P1) `docker ps` failure read as idle | `running_containers` raises RC 5 when `docker ps` fails. Acquire, release, snapshot and restore all stop. | `test_docker_ps_failure_blocks_acquire`, `…_blocks_release` |
| R09-4 (P2) lease released under running containers | Containers started under a lease carry `--label ose.lease=<16 hex of sha256(token)>`. `guest_lease_end` stops only containers with its own label, confirms they are gone, then releases. Otherwise it prints `lease on V KEPT … recovery needed` and exits nonzero. `lease release` refuses while any container runs on the volume. `recovery.sh` uses the same functions, which covers the children's smoke containers. | `ShellLeases`, real `audit-listing.sh`: `docker wait` RC 17 → our container stopped before the release, lease gone; a container that does not stop → lease KEPT, RC≠0; normal run → released. `test_release_refused_while_a_container_runs`. Real guest run: the smoke containers carried their own volume's label (`docker inspect`) |
| R09-5 (P2) `restore --create` mutated Docker before the lease check | `require_lease` moved ahead of `volume inspect/create/chown` | `test_restore_create_with_wrong_token_makes_no_docker_call`, `…_without_any_lease_…`: zero Docker calls |
| R09-6 (P2) whole-environment patching in tests | `load_guest` sets `LEASEDIR`/`SNAPDIR`/`LOGDIR` on the module. Shell tests pass a child environment only. | `test_environment_untouched`; full suite with the reviewer's command `OSE_BASH=… python -I -m unittest discover -s tests/host` → **126 tests OK**, no ResumeAdmission errors |

Other changes: `EVID` in `common.sh` can be overridden (`OSE003_EVIDENCE_DIR`), so the fake `negative-pin` test cannot write into OSE-003's checksummed evidence. `GUEST_STOP_TRIES` sets the stop-confirmation wait. `guest.py` closes its log on exit. The runbook marks Linux hosts unverified and documents RC 7/8, lease-kept recovery and fail-closed Docker.

| Check | RC | Result |
|---|---|---|
| `python -m unittest tests.host.test_guest_harness` | 0 | 36 tests |
| the same 36 tests against the reviewed `dc83bd5` (scratch worktree, new test file only) | — | **15 fail or error**, covering R09-1..R09-5 |
| `OSE_BASH="C:/Program Files/Git/bin/bash.exe" python -I -m unittest discover -s tests/host` | 0 | 126 tests |
| `python -I scripts/check_repo.py` | 0 | |
| `python -I tests/integration/harness/restore_faults_in_image.py --out artifacts/evidence/ose-009/rework-r1` | 0 | success 0, staging-blocked 7, late failure 7 rolled back, rollback failure 8 with the old guest kept |
| `sh tests/integration/harness/recovery.sh` (real guests) | 0 | 15/15 RESULT ok: concurrent smokes and both ports; marker, `kill -9`, survived, restore, smoke, gone; corrupted snapshot refused with the volume unchanged. `runs/20261127T165549Z-1614/` (`SHA256SUMS` 31 entries, `963ccbd29d105ad046828c9b961cb2c29643c263b9337fa851d9b7be3769f54f`); afterwards no running container and no lease |

Evidence for the rework: `artifacts/evidence/ose-009/rework-r1/` (`SHA256SUMS` 2 entries, `c07e8c1a2d196f2e51e23fccfb3970eff26c22ca670817c031a9ec2cc7f840e4`).

Not run: Linux host; a full 50-minute `sysgen.sh run` with the lease (the shell path is covered by the fake-backend tests); leases across two hosts.

Next action: re-review of R09-1..R09-6; after acceptance, the human decides on merge. The manual `Guest lease:` protocol stays until then.

### Independent re-review — 2026-11-27

Reviewer: Codex, high tier, independent of author. Reviewed `6f13967` against `613f777` on `review/OSE-009-r2`, separate worktree `artifacts/review/OSE-009-r2`. **Accepted; all six findings closed; no new findings. OSE-009 VERIFIED, human integration pending.** No implementation changes, merge or push.

- **R09-1 closed:** source and negative-pin target have independent ledger entries, validated before target mutation; target-specific container name/label; cleanup retains original volume/token identities. The prior independent fake-backend reproduction now refuses OTHER-REVIEW-HOLDER's target before any volume removal/start, releases its own source lease and leaves the other lease untouched. The host suite also proves normal negative-pin takes/releases both leases with the target label.
- **R09-2 closed:** users.conf is saved/staged before the swap; late failure rolls back both files, and failed rollback is explicitly RC8 with recoverable old data. Repeated the original blocked-staging fixture as uid1000 in the pinned image: RC7 with OLD_GUEST/OLD_USERS intact. Independently ran the four pinned-image cases: normal success RC0, blocked staging RC7 unchanged, late failure RC7 with exact original bytes, rollback failure RC8 with old data retained. Host tests also cover checksum mismatch and Python RC8 mapping.
- **R09-3 closed:** failed Docker ps is an error, not idle. Original independent failed-query reproduction now returns RC5 for acquisition and require_stopped, without creating a lease. Release also refuses failed queries in the host regressions.
- **R09-4 closed:** labelled ownership is used for cleanup; stops precede release; failed stop/query keeps the lease and returns failure; central release refuses running containers. Original independent failed-wait reproduction now stops its container before removing the lease. Stuck-container and cleanup-query regressions pass. Live independent guests were inspected: each cleanup label exactly matched the first16 SHA256 hex of its own lease token (tokens not saved/printed). Normal end-to-end cleanup left no actual running container or tool lease.
- **R09-5 closed:** ownership is checked before Docker mutation. Original independent unleased --create reproduction now returns RC3 with zero Docker calls. Both wrong-token and absent-lease cases pass in the host suite.
- **R09-6 closed:** load_guest configures module paths without rewriting process environment. Original independent one-test reproduction now leaves same-process native git init RC0 before and after; all previously failing ResumeAdmission fixtures pass in the complete suite.

| Command/check | RC | Result / evidence (relative to this worktree) |
|---|---|---|
| `OSE_BASH=C:/Program Files/Git/bin/bash.exe python -I -m unittest discover -s tests/host -v` | 0 | 126 total: 117 passed, 9 skipped (pinned Sysgen/MVP source caches absent); `artifacts/evidence/review-ose-009-r2/host-tests.txt` and `.rc` |
| `PYTHON=python SRC_VOLUME=ose-sysgen-review-003-20261127 VOL_A=ose-review-009-r2-a VOL_B=ose-review-009-r2-b PORT_A=14370 PORT_B=14371 sh tests/integration/harness/recovery.sh` | 0 | 15/15 RESULT checks pass. Concurrent guests/ports and JES/TSO; marker creation, planned SIGKILL and survival; restore, post-restore JES/TSO and marker absence; corrupt snapshot verify/restore RC6 with unchanged-volume hash. `artifacts/evidence/ose-009/runs/20261127T171821Z-785/summary.txt`; wrapper log/RC under reviewer evidence |
| `python -I tests/integration/harness/restore_faults_in_image.py --out artifacts/evidence/review-ose-009-r2/restore-in-image` | 0 | four cases above in pinned image, expected 0/7/7/8; saved JSON/console/RC |
| `python artifacts/evidence/review-ose-009-r2/original-restore-regression.py` | 0 | assertions of production-uid1000 staging-blocked RC7/unchanged pair pass; fixture/results retained |
| `python artifacts/evidence/review-ose-009-r2/admission-regressions.py`; `environment-regression.py`; `shell-regressions.py` (same directory) | 0 each | prior independent fault reproductions now assert corrected behavior. Fake Docker/Git only for admission/shell tests; no real sysgen/fetch/volume mutation |
| Live label comparison and lease-status capture | 0 | actual per-volume token/label agreement, three ALIVE leases during orchestration; `live-container-labels.json` / `live-tool-leases.txt` |
| Python SHA256 evidence audit | 0 | author rework 2/2 (`c07e8c1a...`), author real recovery 31/31 (`963ccbd2...`), prior independent review 156/156 (`545af9ac...`) unchanged; full hashes in `evidence-audit.json` |
| Final credential scan / container and tool-lease checks | 0 | no guest password in evidence, no running containers, `no leases`; saved reviewer files |
| `python -I scripts/check_repo.py`; `git diff --check` | 0, 0 | repository/docs checks |

Reviewer evidence/fixtures: `artifacts/evidence/review-ose-009-r2/`. Snapshot `artifacts/guest/snapshots/h009-base-20261127t171821z-785/` belongs to this review. Both automatic and manual review leases covered real guest work; released after containers stopped. Only a stopped independent reviewer baseline and fresh disposable `ose-review-009-r2-a` / `ose-review-009-r2-b` were used; author volumes never mounted. Reviewer guests retained stopped. Planned SIGKILL was the isolated acceptance fault, not an unclean shutdown accidentally accepted.

Limits retained: Linux host paths/process liveness, cross-machine leases and a new full 50-minute sysgen were not exercised. Sysgen negative-pin lease behavior was checked through the real shell entry point with fake backends; existing full-build evidence remains separate. Script leases are cooperative within the Docker host/account; manual Docker commands can bypass them. No multi-user security boundary is claimed. The runbook now labels Linux host support unverified.

Following this successful independent review, tasks/README.md and this branch's status now document the reviewed lease tool protocol. The shared author checkout's temporary manual review line was restored; the new instructions take effect through human integration. OSE-014 remains the next platform task; this review does not complete M0a or start package work.

Re-review evidence manifest: `artifacts/evidence/review-ose-009-r2/REVIEW-SHA256SUMS`, 154 files; SHA-256 `60e0834cc75c691933bdc89802ea12cb9501f0af5363db2d473f0a825dcd8f5a`.

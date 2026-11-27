# OSE-009 — Guest lease, snapshot and recovery harness
Status: IMPLEMENTED (2026-11-27; acceptance 1-5 passed on the host and the guest; awaiting independent review)
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

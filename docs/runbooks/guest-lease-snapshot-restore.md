# Runbook: guest leases, isolated guests, snapshots and restore (OSE-009)

Last verified: see the OSE-009 card handoff (dates, commands, RCs). Host: Windows 11, Docker Desktop, Git Bash; the tool is plain Python 3 and the Docker CLI, so Linux works the same.

The harness is package-neutral. A *guest* is a Docker volume holding `sysgen/MVSCE/` (DASD, conf, printers) and `sysgen/users.conf`, as OSE-003 builds it. That is about 180 MB; the sysgen build tree is not needed to run a guest. Tool: `scripts/guest/guest.py`. It logs every command to `artifacts/guest/logs/`.

## Leases: one mutating user per guest
| What | Command | Success | Failure |
|---|---|---|---|
| Take a lease | `python -I scripts/guest/guest.py lease acquire --volume V --task OSE-NNN [--holder-pid P]` | prints a 32-hex token, RC 0 | RC 3 `lease on V is held: task … owner … pid … host … since …`; RC 4 if that holder is gone (STALE); RC 5 if a container already runs on V without a lease |
| See leases | `make lease-status` | one line per lease: ALIVE, STALE or FOREIGN (another host) | |
| Check / release | `… lease check --volume V --token T` / `… lease release --volume V --token T` | RC 0 | RC 3 with the wrong token; RC 4 (check) if the holder died |
| Remove a stale lease | `… lease break --volume V` | RC 0, only if the holder process is gone | RC 3 `refusing to break a alive lease` |

- Leases live in a **host-wide** directory, `OSE_LEASE_DIR`, default `~/.ose-guest/leases`, because Docker volumes are host-wide and several worktrees share them. Creation is atomic (`O_CREAT|O_EXCL`).
- The lease follows a process (`--holder-pid`, default the caller). When that process dies, the lease becomes STALE: it is reported, never taken over silently. A person inspects the guest first, then runs `lease break`.
- **All guest scripts take the lease themselves:** `scripts/smoke.sh`, `scripts/deploy.sh`, `scripts/audit-listing.sh`, and `scripts/sysgen.sh run|negative-pin`. Each acquires the lease on `DASD_VOLUME` for its whole run and releases it on exit. A caller that already holds the lease passes `OSE_LEASE_TOKEN=<token>`, and the script only checks it. A script started on a volume someone else holds stops before it starts any container.
- On Windows the holder PID is the Windows PID (`/proc/$$/winpid` under Git Bash). `os.kill(pid, 0)` would terminate a process on Windows, so liveness is read through the Win32 API.
- Until this tool has been reviewed, also record the lease on the `Guest lease:` line of `docs/status.md` (tasks/README.md "Guest resources").

## Isolated guests and ports
- Each volume is its own guest, and container names carry the volume name (`ose-smoke-<volume>`, `ose-hello-<volume>`, …). So guests on different volumes run side by side.
- Inside each container Hercules listens on 3270/3505/3506; nothing is published by default. For a person's TN3270 session, set `GUEST_TN3270_PORT=13270` (any number). It is published on **127.0.0.1 only**. The guest still uses upstream's published default passwords.

## Snapshots and restore
| What | Command | Success | Failure |
|---|---|---|---|
| Snapshot a stopped guest | `… snapshot create --volume V --name N --token T [--note …]` | `artifacts/guest/snapshots/N/` with `guest.tar`, `files.sha256` (every file), `meta.json`, `SHA256SUMS` | RC 5 if the guest runs; RC 2 if N exists |
| Verify | `… snapshot verify --name N` | `snapshot N OK` | RC 6 `… does not match the manifest (corrupted)` |
| New guest from a snapshot | `… lease acquire --volume NEW …`, then `… restore --volume NEW --name N --token T --create` | `created volume NEW`, `restored snapshot N into NEW` | |
| Restore an existing guest | `make restore DASD_VOLUME=V SNAPSHOT=N OSE_LEASE_TOKEN=T` | `restored snapshot N into V` | RC 6 corrupted snapshot (nothing touched); RC 5 guest running; RC 7 restore failed (previous MVSCE kept) |

How restore protects the guest:
1. `SHA256SUMS` is checked first, before Docker is touched. A corrupted snapshot is refused.
2. The tar is extracted into a scratch directory on the same volume, and every file is checked against `files.sha256`.
3. Only then are the directories swapped. If the swap fails, the previous `MVSCE/` is put back.

## End-to-end test (acceptance 2-4)
`sh tests/integration/harness/recovery.sh` (about 15 minutes) uses two disposable volumes, `ose-h009-a` and `ose-h009-b` (replaced each run), and only reads `ose-sysgen-1` for the baseline snapshot. It runs:
- two concurrent JES2/TSO smokes, on different host ports;
- the marker / `kill -9` / restore / smoke cycle;
- a corrupted-snapshot refusal.

Results are in `artifacts/evidence/ose-009/runs/<UTC>-<pid>/summary.txt`, one `RESULT … ok|FAIL` line per check.

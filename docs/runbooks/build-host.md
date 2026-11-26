# Runbook: build host (OSE-003, ADR-0003 option A)

Last verified: 2026-11-26 on Windows 11, Docker Desktop 29.9.3 (WSL2 backend, 8 CPUs, 16 GB), Git Bash, GNU Make 4.2.1, branch `task/OSE-003-build-host-sysgen`.

The build host is a Debian container pinned by digest. The Windows (or Linux) machine needs only Docker, Git, a POSIX `sh` and Python 3. Nothing is installed on the host, and nothing runs as root inside the container.

## Prerequisites
- A running Docker engine. At least 30 GB free on the drive that holds the repository and Docker's data.
- Network access to github.com and the Debian mirror the first time.

## Steps

| Step | Command | Success looks like | Failure looks like |
|---|---|---|---|
| 1. Build the image | `make fetch` (= `sh scripts/host/hercules-image.sh`) | RC 0, and it prints `HHC01413I Hercules version 4.9.1.11612-SDL-gee86c4de` and `HHC01417I OSE-003 build of ee86c4de…`; `make check` inside the build reports `Did 293 tests.  All OK.` | `image build failed`; read `artifacts/evidence/ose-003/hercules-image-build.log` |
| 2. Check the host | `make doctor` (= `sh scripts/doctor.sh`) | `doctor: all checks passed`, RC 0 | one `FAIL …` line per problem, RC 1 |

The image is `ose-hercules:4.9.1-ee86c4de`:
- Base: `debian@sha256:e67eeead…`.
- Hercules is built from SDL Hercules `ee86c4de` (Release_4.9.1), installed in `/opt/hercules`, and run as uid 1000.
- Hercules' external packages (crypto, decNumber, SoftFloat, telnet) come prebuilt in that source tree. That is why hercules-helper, which would clone them from unpinned branches, is not used.
- Regina REXX is installed only because the Hercules test suite needs it. The built Hercules reports `Without Regina REXX support`, so the `REXX MSGP ON` line in upstream's `conf/local.cnf` gives a harmless `HHC01441E` at start-up.
- `scripts/smoke.sh` adds a thin layer, `…-tools`, with `s3270` and `netbase`.

**A deliberate failure** (acceptance test 1): `DOCTOR_USER=0 sh scripts/doctor.sh` runs the container checks as root. Expected output: `FAIL  running as root (sysgen README: never run as root)` and RC 1. Observed 2026-11-26: RC 1.

## What the doctor checks
- Docker engine reachable.
- Free disk space of at least 30 GB (`MIN_FREE_GB`).
- The pins in `scripts/lib/common.sh` equal `dependencies.lock.json` (hercules, sysgen, rakf, mvp).
- The image exists.
- Inside the container:
  - Debian or Ubuntu, and not root;
  - the Hercules version contains 4.9.1 and names commit `ee86c4d`;
  - `hetinit`, `dasdinit`, `dasdload` and `dasdls` are present;
  - Python 3.9 or later, and git;
  - ports 3270, 3505, 3506 and 8888 are free.

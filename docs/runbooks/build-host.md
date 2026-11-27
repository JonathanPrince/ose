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
- Hercules' external packages (crypto, decNumber, SoftFloat, telnet) come prebuilt in that source tree. That is why hercules-helper, which would clone them from unpinned branches, is not used (ADR-0006, proposed).
- **Debian packages** (ADR-0006, proposed): every apt install reads only from the Debian snapshot `20261123T000000Z`, the base image's own, never the live mirror. Packages OSE drives directly are pinned by version and `.deb` SHA-256 in `upstream/debian/packages.lock.json`. `scripts/lib/debpins.py` generates the install command: download, `sha256sum -c`, and only then install. A hash mismatch stops the image build. The doctor and every smoke run re-check the installed versions.
- Regina REXX (pinned, 3.6-2.4) is installed only because the Hercules test suite needs it. The built Hercules reports `Without Regina REXX support`, so the `REXX MSGP ON` line in upstream's `conf/local.cnf` gives a harmless `HHC01441E` at start-up.
- `scripts/smoke.sh` adds a thin layer, `…-tools-<12 hex>`, with `s3270` 4.1ga10-1.1+b1 and `netbase` 6.4, both pinned. The 12 hex digits are the digest of the pin set (`debpins.py digest tools`), so a layer built under other pins is never reused. Older `…-tools` images without the suffix are ignored and can be deleted.
- A package bump means editing `upstream/debian/packages.lock.json` (snapshot, version, `.deb` SHA-256 from the snapshot's index) and is a task of its own.

The doctor also fails, with `FAIL  in-container checks: docker run exited N` or `… did not complete`, when its container cannot start or stops before its last check (R03-2). It no longer relies only on counting `FAIL` lines.

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

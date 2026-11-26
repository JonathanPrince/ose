# Runbook: build the CC/370 toolchain and compile hello (OSE-004)

Last verified: 2026-11-26, on branch `task/OSE-004-hello-harness`, Windows 11 + Docker Desktop 29.9.3 (Git Bash). **Partial:** compile and assemble only. Link, deploy and run are blocked (see "Blocked steps").

## Prerequisites
- Docker with a running engine. Git and a POSIX `sh` (Git Bash on Windows).
- Network access to github.com and the Debian mirror the first time.
- About 2 GB free under `artifacts/` (git-ignored).

## Commands

| Step | Command | Success looks like | Failure looks like |
|---|---|---|---|
| 1. Toolchain | `sh scripts/build.sh toolchain` | RC 0, and it prints `cc370 1.6.3 (802dde1), based on GCC 3.4.6` plus as370 and ld370 at `802dde1` | RC 1 and `toolchain build failed`; read `artifacts/evidence/ose-004/cc370-build.log` |
| 2. Dialect probes | `PROBE_DIR=<dir with p*.c> sh scripts/build.sh probes` (the OSE-012 probes live on `task/OSE-012-libc-inventory` in `tests/host/c-probes`) | `pNN rc=…` lines in `artifacts/evidence/ose-004/probes/summary.txt` | RC 1: no probe sources, or no toolchain |
| 3. hello | `sh scripts/build.sh hello` | prints the sha256 of `hello.s` and `hello.o`, then **RC 3** "hello link blocked: maclib370 is not an approved dependency" | RC 1: compile error; see the messages above it |

`scripts/build.sh` pins the image by digest and every source by full commit SHA. It refuses a clone that is not at its pin or has local changes. Expected hashes for step 3 at the pins: `hello.o` sha256 `c3a870f9cf30bd9b672a793eb41ebe833a1afc4b8b8637273761a365843a1872`. If it differs, record the new value and the reason before going on.

## Blocked steps
- **Link (load module), `make build`, `make deploy`, batch and TSO runs.** These need `libc.a`, which needs maclib370 (research 2026-11-26-toolchain T-1, which also gives the human's options). Deploy also needs the OSE-003 guest, a lease, and a decision on the transport (T-6, mvsMF).

# 0003 — M0 build host on a Windows workstation
Status: Accepted - Option A
Date: 2026-11-26
Deciders: human maintainer

## Context
- Spec §4 calls for a non-root Debian/Ubuntu build host.
- The pinned Sysgen README (MVS-sysgen/sysgen@4746195d33d9) says "Currently only Debian/Ubuntu based systems are supported". It requires SDL Hercules >= 4.5, recommends building it with wrljet/hercules-helper, and warns against running as root. Confidence: documented. See `docs/research/2026-11-26-upstream-recon.md` R-05.
- The primary workstation (observed 2026-11-26): Windows 11, Docker Desktop with a running engine, one WSL2 distribution (kali-linux, stopped), no Debian/Ubuntu WSL distribution, no `make`, no Hercules, Python 3.14 and Git 2.35.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. Debian/Ubuntu container pinned by image digest, running as a non-root user, with DASD on a bind mount under `artifacts/` | Reproducible, disposable, matches upstream OS, one recipe also serves CI | Hercules timing and performance in a container is not yet measured. The 3270/console ports must be published. Docker Desktop licensing must be checked for the user's context |
| B. Install an Ubuntu LTS WSL2 distribution | Closest to the upstream instructions, simple interactive use | Less reproducible (the distribution drifts), so it needs a provisioning script |
| C. Separate Linux VM or machine | Full isolation | More setup, out of the repo's control |
| D. Kali WSL (already installed) | Nothing to install | Not a supported upstream OS. **Not recommended** |

## Proposed decision
**A**, with **B** as a fallback for interactive debugging. The provisioning steps are scripted in both cases, so `make doctor` checks the same requirements. OSE-003 must show a clean sysgen and IPL on option A before this ADR is Accepted. If A fails, record the failure and propose B.

The `docker-mvsce` image is **not** the build host. It may serve as an optional runtime harness after OSE-002 has checked its licensing and contents.

## Consequences
The guest never depends on the host or container (spec §3). Every host-side command must exit nonzero on failure. Port numbers are configurable so that isolated images can run side by side (OSE-009).

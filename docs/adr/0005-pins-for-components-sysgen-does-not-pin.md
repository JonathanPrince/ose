# 0005 — Pins for components that Sysgen does not pin
Status: Accepted
Date: 2026-11-26
Deciders: human maintainer (pending)
Superseded in part by: ADR-0006 (accepted 2026-11-27), which replaces "built with hercules-helper v0.9.9" in decision 2. The Hercules pin is unchanged.

## Context
ADR-0004 §3 says OSE pins follow what pinned Sysgen installs. Sysgen@4746195d pins its mvslovers products by release and sha256 (`mvslovers.conf`), but does not pin:
- **Hercules**: the README asks only for ">= 4.5" and the code has no version check.
- **MVP**: `git_clone()` takes the default branch, and an existing clone gets `git pull --ff-only` (sysgen.py l.2734, l.3247).
- **The guest C toolchain** (cc370, libc370, mbt): Sysgen installs prebuilt products and does not compile them.

Evidence: `docs/research/2026-11-26-sysgen-pins.md`. Confidence: observed (code read at the pinned commit).

## Decision (proposed)
1. **Toolchain = what the installed UFSD release was built with**: cc370 1.6.3, libc370 2.25.1, mbt 3.0.x (v3.0.1). Source: ufsd `mbt.toml`@v1.5.2, which records that its release was "built and checked with" libc370 2.25.1 and cc370 1.6.3. The libc370 v2.25.1 commit `fcde4e88` matches the UFSD startup banner "LIBC370 2.25.1 (FCDE4E8)". Reason: OSE links libufs and runs beside UFSD, so matching its runtime removes one variable from M0. A newer libc370 (2.29.2 on 2026-11-26) is a deliberate later bump, tested on its own.
2. **Hercules = SDL Hyperion Release_4.9.1** (newest release, which satisfies >= 4.5), built with hercules-helper v0.9.9. OSE-003 must confirm that sysgen completes with it. If it does not, record the failure and pin the version that works.
3. **MVP = main@4c004a59** (2026-11-17). It can only be enforced with a small sysgen change (`upstream/sysgen/MANIFEST.md` P-01) that passes a `ref` for MVP the way RAKF already gets one. That change is offered upstream.

## Alternatives considered
- Newest toolchain (libc370 2.29.2, mbt 3.2.0): more fixes, but untested against the installed UFSD. Kept as the first bump candidate after M0.
- Leaving MVP floating: rejected, because it breaks reproducibility (spec §2).

## Consequences
OSE-003 and OSE-004 build against these pins. Bumps follow ADR-0004 §7. If upstream rejects P-01, OSE carries it as a local patch.

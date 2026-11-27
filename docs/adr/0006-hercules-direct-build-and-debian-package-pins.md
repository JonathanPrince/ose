# 0006 — Build Hercules directly at its pinned commit; pin build-host Debian packages
Status: Proposed
Date: 2026-11-27
Deciders: human maintainer (pending)
Supersedes / superseded by: supersedes ADR-0005 decision 2 only in the words "built with hercules-helper v0.9.9". The Hercules pin itself (SDL Hyperion Release_4.9.1, `ee86c4de`) is unchanged. Origin: OSE-003 independent review 2026-11-27 (dependency note and finding R03-5).

## Context (with evidence links and confidence)
- ADR-0005 §2 chose Hercules 4.9.1 "built with hercules-helper v0.9.9", and the lock's `hercules-helper` entry says it must be used.
- The helper clones Hercules' four external packages (crypto, decNumber, SoftFloat, telnet) from their **default branches**, unpinned (hercules-helper `hyperion-buildall.sh`, recorded in `scripts/host/hercules-image.sh`). That is a mutable fetch, which spec §2 forbids for release builds. Confidence: observed (code read).
- Hercules 4.9.1 at `ee86c4de` already carries prebuilt x86_64 static libraries of those packages in its own tree, and `configure` uses them by default. A direct `configure && make && make check` at the pinned commit therefore has no unpinned inputs from GitHub. Confidence: observed. OSE-003 built it this way twice, the reviewer once more, and a fourth time after this ADR's package pins: `make check` 293/293 each time.
- The build-host image installed Debian packages from the live mirror, unversioned: build tools, Regina REXX (needed by `make check`), and in the tools layer `s3270` (TSO smoke, acceptance test 5) and `netbase`. The reviewer found the s3270 pin unenforced (R03-5) and asked for Regina and netbase to be recorded consistently. Confidence: observed.
- The base image `debian@sha256:e67eeead…` records its own Debian snapshot, `20261123T000000Z`, in `/etc/apt/sources.list.d/debian.sources`. snapshot.debian.org archives are immutable, and apt verifies packages against their signed index.

## Decision
1. **Hercules** is built directly from the pinned commit with the in-tree external libraries (`scripts/host/hercules-image.sh`). hercules-helper is not executed. Its package list stays a reference only. Its lock entry stays as provenance for that list, with a note pointing here.
2. **All apt installs in OSE build-host images** read only from the base image's own snapshot, `20261123T000000Z` (bookworm, bookworm-updates, bookworm-security). The live mirror is not used.
3. **Packages that OSE drives directly** are pinned by exact version **and** `.deb` SHA-256 in `upstream/debian/packages.lock.json`. They are downloaded, hash-checked **before** installation, and version-checked again on every use (doctor, smoke). Today these are regina-rexx, libregina3 and libregina3-dev in the Hercules image, and s3270 and netbase in the tools layer.
4. Other build packages (gcc, make, cmake and so on) are fixed by the snapshot alone; their installed versions are recorded as evidence. They only build Hercules, which is then checked by its own test suite, version string and commit.
5. The tools image tag carries a digest of its pin set (`…-tools-<12 hex>`), so an image built under different pins is never reused under the same name.
6. Build-host Debian packages live in `upstream/debian/packages.lock.json` and not in `dependencies.lock.json`. The root lock's schema requires a 40-hex upstream commit, and these are binary distribution packages. Both files are authoritative for their own scope.

## Alternatives considered
- **Keep hercules-helper.** Rejected: it fetches the external packages unpinned. Pinning it would mean patching the helper for no gain over the in-tree libraries.
- **Build s3270 from x3270 source at a pinned tag.** Possible, but it needs its own build chain and gives nothing for a test-only tool. Kept as the fallback if Debian drops the snapshot.
- **Pin only by version (`apt-get install s3270=4.1ga10-1.1+b1`) against the live mirror.** Rejected: old versions disappear from the live mirror, so the build would break rather than reproduce.
- **A prebuilt tools image pinned by digest.** Needs a registry and image provenance. Revisit if OSE gets CI with a registry.

## Consequences (incl. what would make us revisit)
- Builds depend on snapshot.debian.org being reachable. It is sometimes slow; apt retries 5 times. If it becomes unreliable, mirror the pinned `.deb` files into `artifacts/cache/` by hash.
- A package bump is a deliberate edit of `upstream/debian/packages.lock.json` (new snapshot, versions and hashes), done as its own task (ADR-0004 §7).
- Revisit decision 1 if a later Hercules release drops its in-tree external libraries.
- Licensing: Regina LGPL-2.0-or-later and netbase GPL-2.0 (from their Debian copyright files). s3270's x3270 licence family is recorded as UNRESOLVED (BSD-style texts, not mapped to SPDX). None of these are redistributed; they are build and test tools only.

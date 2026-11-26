# 0004 — Dependency pinning and upstream patch policy
Status: Accepted
Date: 2026-11-26
Deciders: human maintainer (pending)

## Context
Spec §2 requires each dependency to record its commit, version, checksum, license, source URL, patch set and verification date, and forbids mutable "latest" downloads in release builds. Upstream is very active (most repositories were pushed in November 2026), so the drift risk is high.

## Decision
1. `dependencies.lock.json` at the repo root is authoritative. Its schema is in `upstream/README.md` and `scripts/check_repo.py` checks it.
2. Every entry pins a full 40-hex commit SHA. A tag or release is recorded as well where one exists, but the SHA is authoritative. For downloaded release assets, record the asset URL and its SHA-256.
3. **The OSE pin follows what pinned Sysgen installs.** For example, if Sysgen at the pinned commit installs UFSD 1.5.2, OSE pins UFSD at the commit for 1.5.2, not at UFSD HEAD. Any deviation needs its own ADR.
4. Upstream source is not vendored into this repository. `upstream/<component>/` holds only a manifest and `patches/NNNN-*.patch`, which are small and reviewable and are offered upstream.
5. Fetched sources go to a cache outside Git (`artifacts/cache/`) and are checked against the lock.
6. `license_spdx` comes from reading the LICENSE file at the pinned commit, not from GitHub API metadata. When rights are unclear, use `"UNRESOLVED"` and add a note. Unresolved entries block redistribution, not local use.
7. A version bump is a task of its own, with re-verification and test evidence.

## Consequences
Builds are reproducible offline once the cache is warm. Upstream fixes arrive only through deliberate bumps.

# Upstream manifests and patches

ADR-0004 governs this directory. No upstream source is vendored here.

```
upstream/<component>/MANIFEST.md          # what we use, why, build notes, upstream contacts
upstream/<component>/patches/NNNN-*.patch # minimal, reviewable, offered upstream
```

## `dependencies.lock.json` schema (v1)

```json
{
  "schema_version": 1,
  "components": [
    {
      "name": "ufsd",
      "role": "filesystem STC + libufs",
      "source_url": "https://github.com/mvslovers/ufsd",
      "commit": "<40-hex SHA>",
      "version": "1.5.2",
      "tag": "<tag or null>",
      "artifacts": [{"url": "<release asset url>", "sha256": "<64-hex>"}],
      "license_spdx": "MIT | UNRESOLVED | ...",
      "license_evidence": "LICENSE@<sha> (read by OSE-002)",
      "redistribution": "permitted | not-permitted | UNRESOLVED",
      "patches": [],
      "pinned_by": "sysgen@<sha> README l.185 | ADR-NNNN",
      "verified_date": "YYYY-MM-DD",
      "verified_by": "OSE-002 (tier)",
      "notes": ""
    }
  ]
}
```

`scripts/check_repo.py` checks the required keys and the SHA format.

Two optional top-level lists were added in the OSE-002 rework:

```json
"excluded": [
  {"name": "ufs370", "source_url": "...", "observed_head": "<sha or null>",
   "reason": "why it is not a dependency", "evidence": "where that was established",
   "revisit": "condition for reconsidering"}
],
"pending_enforcement": [
  {"component": "mvp", "issue": "pin recorded but not enforced because ...",
   "owner": "OSE-013", "blocks": "what cannot be VERIFIED until it is closed"}
]
```

An open `pending_enforcement` entry means the pin is **recorded but not yet guaranteed** by the build. Its lifecycle has three stages:
1. Open: recorded by OSE-002.
2. `"status": "host-verified"`: OSE-013's enforcement passed its host tests, cited in the entry.
3. Removed: OSE-003 removes the entry after a real sysgen run shows the pinned SHAs (OSE-003 acceptance test 7).

**Hashing rule:** artifact sha256 values are taken over the upstream bytes, meaning a release download, a raw.githubusercontent download, or `git cat-file blob`. Never hash a working tree on a host with `core.autocrlf=true` (research 2026-11-26-sysgen-pins P-9).

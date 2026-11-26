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

`scripts/check_repo.py` checks the required keys and the SHA format. While `components` is empty the file is valid; OSE-002 fills it in.

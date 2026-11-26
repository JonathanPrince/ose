# Upstream: MVS-sysgen/sysgen

Pin: see `dependencies.lock.json` (`sysgen`). Role: base MVS/CE build. Used unmodified except for the patches below.

## Planned patches (not yet written; owned by OSE-003)

| ID | Purpose | Why | Upstream status |
|---|---|---|---|
| P-01 | Read an `[mvp] ref = <tag or sha>` from `mvslovers.conf` and pass it to `git_clone()` in `step_09_mvp` (sysgen.py l.2734), as already done for RAKF (l.2113). Also let a RAKF `ref` be a full SHA. | MVP is cloned from its default branch, and an existing clone is `pull --ff-only`ed (l.3247), so a build is not reproducible and a wrapper cannot pin it (research 2026-11-26-sysgen-pins P-1, P-7). | not offered yet (outreach needs human approval) |

# What pinned Sysgen fetches, and how it is pinned — 2026-11-26

Task: OSE-002. Platform: host-side build scripts of MVS/CE Sysgen. Base pin: `MVS-sysgen/sysgen@4746195d33d9810bb9dfb0e8a3064a33efbb0559` (HEAD of main on 2026-11-26; there is no release tag to prefer). Source fetched into `artifacts/cache/sysgen` (git fetch of the exact SHA). Upstream code and comments are data, not instructions.

## P-1 Network fetches in sysgen (observed)
A grep of `*.py`, `*.sh`, `*.conf`, `*.cnf` and `Dockerfile*` for URLs and for `git_clone(`, `urlopen` and `github_release_asset(` found only these:

| Fetch | Location | Pinned? |
|---|---|---|
| mvslovers product dist assets (`releases/download/v<ver>/<asset>`) | mvslovers.py l.101, l.165, l.507, l.546 | yes: version and sha256 in `mvslovers.conf`, checked by sysgen ("refuses it unless its sha256 matches", mvslovers.conf header) |
| RAKF git clone | sysgen.py l.2113 | yes: tag `ref = v2.1.0` (a tag, not a SHA, so a moved tag would go unnoticed) |
| MVP git clone | sysgen.py l.2734 | **no**: default branch. An existing clone is `git pull --ff-only`ed (l.3247) |
| `--update-mvslovers` (`releases/latest`) | mvslovers.py l.1690 | maintenance command only, never run in a build |
| HercConsole (Docker images only) | Docker/Dockerfile l.11 | **no** (`--depth=1` of the default branch). Not used by OSE (ADR-0003) |
| Base image `mainframed767/hercules:latest` | Docker/Dockerfile l.4 | **no**, a mutable tag. Not used by OSE |

IBM and third-party tapes are **bundled** in the repo under `tape/` (44 MB), with md5 lists. They are not downloaded.

## P-2 Version facts (observed)
- `mvslovers.conf` pins brexx370 3.1.0 (plus ZMG0001), ufsd 1.5.2, ftpd 1.3.4, httpd 4.5.1, mvsmf 1.4.1, sdsf 1.2.0, RAKF **v2.1.0** and ufsd-utils 1.0.1.
- **Correction to recon R-02:** the README (l.184) says RAKF v2.0.0. The configuration the code reads says v2.1.0, so the README is stale. v2.0.0 = a4d101e8, v2.1.0 = 941b07dc.
- There is no Hercules version check in sysgen.py (grep for version/hercules). The ">= 4.5" requirement appears only in the README (l.10).

## P-3 Independent asset verification (observed)
All 9 assets were downloaded from GitHub release URLs into `artifacts/cache/assets/`. The sha256 values were computed locally with `sha256sum` and all 9 **MATCH** `mvslovers.conf`: brexx370 dist, ZMG0001.xmit, ZMG0001.zip, ufsd, ftpd, httpd, mvsmf and sdsf dists, and ufsd-utils linux-amd64. The values are recorded in `dependencies.lock.json`.

## P-4 Tag → commit resolution (observed, `git ls-remote`, 2026-11-26)
Where a tag is annotated, the lock records the peeled commit (`^{}`): brexx370, ftpd, httpd, mvsmf, cc370, libc370 and mbt. ufsd, sdsf, RAKF, ufsd-utils, hyperion and hercules-helper use lightweight tags, so the tag SHA is the commit.

## P-5 Toolchain used for the installed products (documented by upstream)
ufsd `mbt.toml`@v1.5.2 records `cc370 = "1.6.3"`, `libc370 = "2.25.1"` and `mbt = "3.0"`, and says the release candidate's banner read "UFSD005I LIBC370 2.25.1 (FCDE4E8)". The libc370 v2.25.1 peeled commit is `fcde4e88…`, which matches. This feeds ADR-0005.

## P-6 Leads for other tasks (documented in upstream comments, unverified)
Each is a pointer to verify, not a finding.
- **OSE-005 / OSE-007:** libufs calls `iefssreq()` (SVC 34) (ufsd mbt.toml, TSTLIBUF comment). As of libc370 2.23.0, `iefssreq()` "refuses an unauthorized caller with -1/EPERM instead of S047" (libc370#402). Does an ordinary libufs client need authorization, and if so how does it get it? This bears directly on the identity model.
- **OSE-005:** the module `UFSDSSIR` ("SSI thin router") is loaded into **CSA**. UFSD uses key-0 windows (`__loadhi()`), and its request and buffer pools use CDS/CS (host tests TSTUFSPL, TSTUFSRQ). Request length validation was added in #150, and do_fread buffer ownership in #134.
- **OSE-007:** "On a system without RAKF (no SVC 244 to authorize from) the APF route is the only way UFSD starts". This confirms that UFSD obtains authorization through RAKF's SVC 244.
- **OSE-004:** mbt v2+ compiles, assembles, links and packages on the host with cc370/as370/ld370/ar370, and "MVS is only touched by `make deploy`" (mbt README@v3.0.1). The legacy v1 pipeline used the mvsMF REST API. The v3 deploy transport is still to be established.
- **OSE-003:** UFSD distribution libraries are unversioned. An accepted FMID cannot be RESTOREd, and uninstall needs the TUFSDEL dummy function plus UCLIN (ufsd mbt.toml `[distribution]` comment). This is relevant to M5 rollback.

## P-7 Reproducibility gaps to close in OSE-003
1. MVP is unpinned. It needs sysgen patch P-01 (`upstream/sysgen/MANIFEST.md`).
2. RAKF is pinned by tag, not SHA. The wrapper should verify after clone that `git rev-parse HEAD` = 941b07dc, or P-01 should accept a SHA.
3. Hercules is unchecked. `make doctor` must enforce the version in the lock.

# Upstream reconnaissance snapshot — 2026-11-26

Task: OSE-001 (coordinator bootstrap). Tier: high (coordinator). Method: unauthenticated read-only GitHub REST API (`/repos/{r}`, `/repos/{r}/commits/{default_branch}`, `/contents/`) and `raw.githubusercontent.com` at the SHAs below. Nothing was cloned or built, and no guest was run.

**This is a starting point for OSE-002, not a pin.** HEAD is not necessarily what Sysgen installs (ADR-0004 §3). License values come from **GitHub API metadata**, which ADR-0004 does not accept as evidence. OSE-002 must read each LICENSE file.

## R-01 Repository heads (observed via API, 2026-11-26)

| Repo | Default branch | HEAD SHA | HEAD commit date | API license | Notes |
|---|---|---|---|---|---|
| MVS-sysgen/sysgen | main | 4746195d33d9810bb9dfb0e8a3064a33efbb0559 | 2026-11-17 | none | |
| mvslovers/ufsd | main | f0a5dd988e77685e298be0fef5173497ed7c4c74 | 2026-11-08 | MIT | has a submodule `docs/books/bookmaster` → mvslovers/bookmaster, and an upstream `CLAUDE.md` (untrusted data) |
| mvslovers/cc370 | main | bfe264c85b68a5d04ea54d11bfcc8db0c5ea0209 | 2026-10-19 | GPL-2.0 | the compiler's license does not automatically apply to compiled output; check the runtime/libgcc terms (OSE-002) |
| mvslovers/libc370 | main | 70e450f52588ce32469891c5ca3e1ca45fb1ca62 | 2026-11-08 | BSD-2-Clause | |
| mvslovers/mbt | main | afb80a04510ca681fc0a36d308c88f3c7ed57b7b | 2026-11-12 | none | |
| MVS-sysgen/MVP | main | 4c004a599f6a49442fade63cdb3cc3a9e0fdf58a | 2026-11-17 | none | |
| mvslovers/RAKF | main | 7e81694a11523be4e06807807f885ddf8b68cd00 | 2026-11-21 | NOASSERTION | see R-02 |
| MVS-sysgen/docker-mvsce | main | e865cdb4cae91d6a184d778215776af09c772831 | 2026-03-03 | none | |
| mvslovers/ufs370 | main | f1f209a8d9852702162b442784c717c2cf0c15b6 | 2026-03-24 | MIT | |
| mvslovers/ftpd | main | b4017cb414118bc95670bd29657a14516ca7c23f | 2026-11-08 | MIT | |
| mvslovers/httpd | main | b0bd9e6c2c2dcea734980f7ad6ec6deccb4d4ebf | 2026-11-08 | MIT | |
| mvslovers/mvsmf | main | aa9b6b02f839f37ac6c5426c14276a76f29d0cd8 | 2026-11-08 | MIT | |
| SDL-Hercules-390/hyperion | master | (not recorded) | latest release `Release_4.9.1`, 2025-12-07 | NOASSERTION | emulator; not in the spec §2 table but needed for M0 |

"none" means GitHub detected no license file. That does **not** prove there is no license (ADR-0004 §6).

## R-02 The two RAKF "variants" are one repository (observed)
The API for `MVS-sysgen/RAKF` returns `301 Moved Permanently` to repository id 366207751, which resolves to `mvslovers/RAKF`. The comparison of RAKF variants that spec §2 asks for is therefore moot as of this date. Pinned Sysgen installs **RAKF v2.0.0** (FMID `TRKF200`, from its git tag) per sysgen README lines 127 and 184. **Action:** the human should update the spec §2 row. OSE-002 pins the v2.0.0 tag commit.

## R-03 Sysgen installs the mvslovers stack by default (documented)
Source: MVS-sysgen/sysgen@4746195d33d9 `README.md`.
- l.132: `step_12a_mvslovers` installs "UFSD, FTPD, HTTPD and mvsMF with SMP, their site configuration and UFS disks, and a start/stop smoke test".
- l.185: UFSD **1.5.2**, FMID `TUFS152`, REC APP ACC, data sets `UFSD.*`.
- l.74: "UFSD, HTTPD and FTPD are not started at IPL". l.72: HTTPD and mvsMF serve under `/zosmf` on port 8080 once started.
- l.202–203: UFS disks are `UFSD.ROOT` for `/`, `HTTPD.WEBROOT.UFS` for `/www`, `UFSD.SCRATCH` for `/tmp`, and `<USER>.UFSHOME` for `/u/<user>`.
- l.134, l.252–254: `step_13_customize` runs `jcl/customize.jcl` (default OPNTERSE with MVP). This confirms the post-generation hook that spec §2 claims.

**Implications (hypotheses for OSE-005/007):** the existing home convention is `/u/<user>`, whereas spec §3.3 says `/home`. Alternate access paths to UFS (FTPD, HTTPD, mvsMF) are already installed, though not started.

## R-04 Authorization model of the mvslovers servers (documented; security-relevant)
sysgen README l.198: "UFSD, FTPD, HTTPD, mvsMF run authorized through RAKF's SVC 244 (no APF entries)". Questions for OSE-007 (high tier):
1. What does SVC 244 grant, and to which callers? How does it decide who may become authorized?
2. Can an unprivileged user program use the same route?
3. How does UFSD learn the identity of the requesting user?
Nothing is concluded here.

## R-05 Build host requirements (documented)
sysgen README l.10: "hercules SDL >= 4.5". l.107: build Hercules with wrljet/hercules-helper. l.111: "Currently only Debian/Ubuntu based systems are supported." l.113: do not run as root (an upstream-reported Hercules resource bug). l.143: the default sysgen timeout is 30 minutes and can deadlock. These feed ADR-0003 and OSE-003.

## R-06 Default RAKF profiles (observed text; meaning is a hypothesis)
`profiles.conf` at the pinned sysgen commit begins with `DATASET * READ` and `DATASET * ADMIN ALTER` (column layout: class, resource, group, access). **Hypothesis:** every user has READ on every data set not matched more specifically. If so, UFSD backing data sets such as `UFSD.ROOT` and `<USER>.UFSHOME` can be read directly, bypassing any UFS permission bits (spec §3.3 and §3.4, "alternate access"). OSE-007 must confirm the format and the effective access with a negative guest test.

## R-07 Workstation (observed)
Windows 11. Tools present: Docker Desktop (running), WSL2 `kali-linux` (stopped), git 2.35.1, gh (not authenticated), Python 3.14.4, jq, curl. Missing: make, Hercules, any Debian/Ubuntu WSL distribution. See ADR-0003.

## Not yet verified (to be checked)
- What Sysgen actually pins for cc370, libc370, mbt, ufs370, brexx, hercules-helper, and the release assets it downloads (sysgen README l.232: "download the … dist releases"). Owner: OSE-002.
- Whether UFSD uses IEFSSREQ/SVC 34 as spec §2 says. Owner: OSE-005.
- Hercules license text (QPL is expected but unconfirmed). Owner: OSE-002.

## Corrections (appended 2026-11-26, OSE-002)
- **R-02:** the RAKF version Sysgen actually installs is **v2.1.0** (`mvslovers.conf` `[rakf] ref = v2.1.0`, read by sysgen.py l.2113). README l.184 says v2.0.0 and is stale. The redirect finding stands. See `2026-11-26-sysgen-pins.md` P-2.
- **R-01:** the HEAD SHAs above are **not** the pins. Pins are in `dependencies.lock.json`. For example, UFSD is pinned at v1.5.2 = 1a63bf52, not HEAD f0a5dd98.

# Licensing and redistribution inventory — 2026-11-26

Task: OSE-002. **This is a fact inventory, not legal advice.** Every "UNRESOLVED" item is a question for the human maintainer, who decides on redistribution, the public repository and outreach (spec §9).

Method: fetched `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING`, `COPYING.txt`, `LICENCE` and `license.txt` from `raw.githubusercontent.com/<repo>/<pinned sha>/`. Where none existed: listed the repository root at that SHA (GitHub trees API) and grepped `README.md` for license, copyright, MIT and GPL. Copies of the files are in `artifacts/cache/licenses/` (not committed).

| Component | Evidence at pin | SPDX (as read) | Redistribution |
|---|---|---|---|
| sysgen | no license file; README silent | — | UNRESOLVED |
| IBM MVS 3.7 starter and 3.8j distribution tapes (bundled in sysgen `tape/`) | `tape/README.md` names the source (jaymoseley.com, CBT CD-ROM 5, 2000-12-06); no rights statement | — | UNRESOLVED |
| Other bundled tapes (ptfs, rpf184, apvtmacs, j90012) and `documentation/*.pdf` (IBM manuals) | no rights statement | — | UNRESOLVED |
| MVP (with its bundled packages) | no license file; README silent | — | UNRESOLVED |
| RAKF v2.1.0 | `LICENSE`: "COPYRIGHT (C) 1991 BY CRAIG J. YASUNA. ALL RIGHTS RESERVED … MUST NOT BE SOLD, GIVEN, OR OTHERWISE DISTRIBUTED TO ANY OTHER COMPANY WITHOUT THE PRIOR WRITTEN PERMISSION … NOT 'PUBLIC-DOMAIN', BUT … PERMISSION THAT IT BE DISTRIBUTED ON THE CBT MVS MODS TAPE", followed by a 2011 e-mail in which the author welcomes continued distribution | custom, restrictive | UNRESOLVED |
| brexx370 3.1.0 | `COPYING`: GNU GPL v2 | GPL-2.0 (only/or-later not determined) | permitted, with GPL source obligations |
| ufsd 1.5.2, ftpd 1.3.4, httpd 4.5.1, mvsmf 1.4.1 | `LICENSE`: MIT | MIT | permitted |
| sdsf 1.2.0 | no license file; README silent; the dist tarball has no license | — | UNRESOLVED |
| ufsd-utils 1.0.1 | README "License: MIT"; no license text | MIT (declared) | UNRESOLVED (attribution text missing) |
| cc370 1.6.3 | `COPYING`: GNU GPL v2 | GPL-2.0 | permitted, with GPL source obligations |
| libc370 2.25.1 | `LICENSE`: BSD 2-clause | BSD-2-Clause | permitted (keep the notice) |
| mbt 3.0.1 | no license file; README silent | — | UNRESOLVED (affects use only if OSE redistributes mbt or derived scripts) |
| SDL Hercules 4.9.1 | `COPYRIGHT`: "may be distributed under the terms of the Q Public License Version 1.0"; `LICENSES/` directory not read | QPL-1.0 | permitted under QPL conditions (not reviewed in detail) |
| hercules-helper 0.9.9 | `LICENSE`: MIT | MIT | permitted |

## Questions for the human maintainer
1. **Generated MVS/CE images** contain the IBM base, RAKF, SDSF, MVP packages and others. Until questions 2–4 are settled, should OSE ship only scripts and patches (the spec §2 default), never DASD images?
2. **RAKF:** its license forbids distribution "to any other company" without written permission. OSE will depend on RAKF behavior and may want to propose patches. Should OSE limit itself to describing changes and contributing upstream, and never redistribute RAKF source or binaries?
3. **Repositories without a license** (sysgen, MVP, sdsf, mbt; ufsd-utils has no license text): ask the maintainers to add licenses before OSE depends on redistributing anything from them? This counts as external outreach, so the human decides.
4. **Compiled OSE programs:** do binaries built with cc370 (GPL-2.0) include compiler support code that carries GPL obligations, as libgcc would without its exception? Needs a check of what cc370 links in (OSE-004 can list the linked members).
5. **OSE's own license:** not chosen. It must be compatible with linking libc370 (BSD-2) and libufs (MIT), and with any GPL obligations from question 4.

None of these block **local** M0 work (building and testing on our own host). They block redistribution and M5.

## Addendum (OSE-002 rework 1, 2026-11-26, after review)

### Corrections to the table above
Under ADR-0004 §6, an SPDX value is given only where a license text was read at the pin.
- **ufsd-utils** → `UNRESOLVED`. The README declares MIT, but no license text exists.
- **brexx370** → `UNRESOLVED` (license and redistribution). COPYING is the GPL v2 text. README l.123–132 says "licensed under the GNU General Public License, version 2 (GPL-2.0)" and lists bundled New BSD (`fss/`, `src/rxtso.c`, `inc/rxtso.h`), MIT (`map/`) and Unlicense (`regex/`) parts. Whether it is "only" or "or later" is not established from what was read.
- **cc370** → `UNRESOLVED` for the same only/or-later reason; GCC 3.4.6-lineage headers were not read.
- **Hercules** → `UNRESOLVED` (license and redistribution). COPYRIGHT says QPL-1.0, but `LICENSES/` also holds crypto, decNumber (ICU), SoftFloat and telnet licenses plus `herclic.html`, none of which have been read.

### MVP packages installed by sysgen (review finding 1)
Scan method: each package file at MVP@4c004a59 was searched for license, copyright, (c), public domain, GPL, MIT, freeware and permission wording. Text packages were read as ASCII; the XMI packages ISPF, OPNTERSE and REVIEW were decoded as cp037. Per-package evidence is in the `mvp-pkg-*` entries of `dependencies.lock.json`. All 22 are `UNRESOLVED`.

| Rights evidence found | Packages |
|---|---|
| "Copyright (C) … Larry Belmontes, Jr.", AS-IS disclaimer, request to keep the author's name, reference to the "MVS 3.8J hobbyist public domain community"; **no explicit grant** | DFSPC, DALCDS, DUCBD, CCOMPR, FINDSRCH, ISPOPT5, WRLDWTCH, GETDTE, CHKDSN, LISTDSJ, CUTIL00 (ISPTHEME embeds the same notices) |
| "COPYRIGHT 2021, WALLY MCLAUGHLIN" in members; no grant found | ISPF |
| TK4- manual statement quoted: "put into the public domain without claiming any copyright by the author as far as no third party copyrights are affected"; the content may include IBM macros | MACLIB |
| "COPYRIGHT = NONE" | PRINTOFF |
| Second-hand note: the Xephon copyright "no longer applies", and posting permission was obtained from SDS | PUTCARD |
| No rights text found | NJE38 (homepage github.com/moshix/nje38mvs, not read), OPNTERSE, REVIEW (homepage prycroft6.com.au, not read), ULXL01, COMPARE (CBT File 296), VTOC (CBT ware, 1968 MIT Instrumentation Laboratory author line) |

### Additional questions for the human maintainer
6. **Hercules:** read `LICENSES/` (QPL-1.0 plus the crypto, decNumber/ICU, SoftFloat and telnet terms) before any statement about redistributing Hercules or a container image that contains it.
7. **UFSD:** its README says the on-disk format code was "originally contributed to The NetBSD Foundation by UCHIYAMA Yasushi". Do BSD notices have to be kept alongside UFSD's MIT license when OSE ships anything derived from libufs or UFSD source?
8. **MVP packages:** the Belmontes notices assert copyright without granting redistribution. ISPF (McLaughlin) and several CBT-derived packages carry no grant either. Combined with question 1, this supports shipping **scripts only, never images**. Should OSE ask the authors for explicit terms? (Outreach: the human decides.)
9. **brexx370 and cc370:** settle GPL-2.0-only vs -or-later by reading source headers, before OSE ships anything that links or bundles them.


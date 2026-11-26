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

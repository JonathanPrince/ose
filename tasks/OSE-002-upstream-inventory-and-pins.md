# OSE-002 — Inventory upstream versions and licenses; pin dependencies
Status: MERGED (VERIFIED 2026-11-26; merged to main 5970f87; records pins only, enforcement in OSE-013)
Milestone: M0
Dependencies: OSE-001
Owner: coordinator session (2026-11-26)
Risk: medium (licensing affects redistribution)
Model tier: economy (extraction); can be split per component
Reviewer tier: standard; licensing conclusions go to the human
Budget: local-only
Branch: task/OSE-002-upstream-inventory
Guest resources: none
Baseline commit: none (no commits yet; work done in the uncommitted bootstrap tree)

## Goal and non-goals
Goal: fill `dependencies.lock.json` (schema in `upstream/README.md`) for every component that pinned Sysgen installs or that OSE M0 needs. Record the provenance and the rights questions that remain open.
Non-goals: building anything, judging code quality, choosing between alternatives, legal conclusions (list the open questions instead).

**Scope amendment (decided by the human maintainer, 2026-11-26, after review finding 3):** OSE-002 covers **recording** the pins. **Enforcing** them in the build belongs to OSE-013. A pin that cannot be enforced at the moment does not block OSE-002, provided it is recorded under `pending_enforcement` in the lock with OSE-013 as owner. The amended escalation rule is below. This amendment was made after rework 1 was submitted for re-review; the reviewer should judge against the amended gate.

## Inputs and primary references
- spec §2; ADR-0004; `docs/research/2026-11-26-upstream-recon.md` (starting HEADs, R-02 RAKF redirect).
- MVS-sysgen/sysgen at the commit chosen as the base pin (start from 4746195d33d9 unless there is a newer tagged release; record the reason). Read `sysgen.py`, `mvslovers.py`, `mvslovers.conf`, `sysgen.conf`, the README "dist releases" section, and every URL or tag those files fetch.
- Components: sysgen, SDL Hercules (the version sysgen expects) and hercules-helper, RAKF (v2.0.0 tag), UFSD (1.5.2), FTPD, HTTPD, mvsMF, UFS370, CC/370, LIBC/370, MBT, MVP, BREXX/370, docker-mvsce (optional), and everything else sysgen downloads.
- IBM MVS 3.8j distribution materials: record the claims about their status with sources. Do not conclude anything.

## Allowed files / interfaces
`dependencies.lock.json`, `upstream/<component>/MANIFEST.md`, `docs/research/YYYY-MM-DD-licensing.md`, `docs/research/YYYY-MM-DD-sysgen-pins.md`, this card, `tasks/usage.jsonl`. Fetched data goes only to `artifacts/cache/`.

## Acceptance tests (commands and expected outcomes)
1. `python3 scripts/check_repo.py` → RC 0. The lock has at least 12 components, each with a 40-hex `commit`.
2. For every entry, `git ls-remote <source_url>` (or the release API) shows the pinned SHA exists. The reviewer spot-checks at least 3 entries by hand and records the commands and output.
3. Every `version` that Sysgen installs is traced to a file and line in sysgen at the pinned commit (`pinned_by`).
4. Every `license_spdx` is backed by a LICENSE file or source header read at the pinned commit. Anything unclear is `UNRESOLVED` with a note. The licensing note lists every unresolved redistribution question for the human.
5. Each release asset has a sha256 computed from a real download, with the command recorded.

## Escalation triggers
- Sysgen fetches a mutable URL that cannot be pinned → record the intended pin and its content hashes, add a `pending_enforcement` entry owned by OSE-013, and list the fetch in the research note. Go to BLOCKED only if no pin or hash can be recorded at all. (Amended 2026-11-26 by the human; the original rule was "→ BLOCKED; propose a cache-and-hash approach".)
- Conflicting license statements → human.
- A component needs authentication to fetch → stop.

## Handoff

### Rework 2 (2026-11-26, response to the re-review of rework 1)
The re-review confirmed that original findings 1–3 are fixed. It raised a **new P2, a circular completion gate**. The re-review was written before the human's scope amendment, which is why its record still describes OSE-002 as BLOCKED.
- **OSE-002 ↔ OSE-013 leg:** removed by the human's scope amendment (see "Scope amendment"). OSE-002 records pins only. Open `pending_enforcement` entries owned by OSE-013 no longer hold this card.
- **OSE-003 ↔ OSE-013 leg:** fixed by changing card text only.
  - OSE-013 now completes on host-verified enforcement (its tests 1–6). Its old test 5, which needed the OSE-003 sysgen run, was replaced by an interface hand-off test.
  - The end-to-end proof is now **OSE-003 acceptance test 7**: the pinned SHAs and package hashes appear in a real sysgen log, a wrong pin fails closed, and the `pending_enforcement` entries are then removed.
  - The resulting order is acyclic: OSE-002 → OSE-013 → OSE-003. The pin-enforcement lifecycle (open → host-verified → removed) is documented in `upstream/README.md`.
- Pin verification is not weakened. It moves to the task that can actually run it.
- Changed files: `tasks/OSE-013-*.md` (tests 5–6 plus a completion-boundary note), `tasks/OSE-003-*.md` (test 7), `upstream/README.md`, this card, the lock's `pending_enforcement[0].blocks` text, `docs/status.md`.
- Commands: `python -I scripts/check_repo.py` and `python -I -m unittest discover -s tests/host`. Results are recorded in the usage log entry for this attempt.

Next action: the reviewer confirms that the sequencing fix resolves the P2. If so, OSE-002 → VERIFIED.

### Rework 1 (2026-11-26, after review "changes requested"; branch `task/OSE-002-upstream-inventory`, base `26dd7a6`)
Response to each review finding:
- **Finding 1 (P1), fixed.** Added 22 `mvp-pkg-*` entries: the four packages sysgen installs (NJE38 via `jcl/nje38.jcl` l.12; ISPF and ISPTHEME via `jcl/ispf.jcl` l.12–13; OPNTERSE via `jcl/customize.jcl` l.13) plus their full `Depends:` closure from MVP `desc/` (REVIEW, DFSPC, DALCDS, DUCBD, CCOMPR, FINDSRCH, ISPOPT5, ULXL01, WRLDWTCH, MACLIB, GETDTE, COMPARE, PRINTOFF, CHKDSN, LISTDSJ, CUTIL00, VTOC, PUTCARD). Each entry pins the containing MVP commit, the version from MVP `cache`, and a sha256 of the package file. Rights evidence comes from scanning each package (text packages as ASCII, XMI packages decoded as cp037); every package is `UNRESOLVED`. UFS370 and docker-mvsce are recorded under a new `excluded` list with evidence and a revisit condition.
- **Finding 2 (P2), fixed.** ufsd-utils, brexx370 and hercules now have `license_spdx` UNRESOLVED (brexx370 and hercules also have `redistribution` UNRESOLVED), with the evidence quoted. cc370 is changed the same way for consistency (same only/or-later gap). Licensing note questions 6–9 added. Acceptance test 4 is re-stated below.
- **Finding 3 (P2), accepted.** Attempt 1 wrongly treated proposing P-01 as meeting the escalation rule. This card is now **BLOCKED**. Enforcement is owned by the new card **OSE-013** (enforce MVP and RAKF pins), and the lock records it under `pending_enforcement`. Alternative for the human: amend this card's gate so OSE-002 covers *recording* the pins and OSE-013 covers *enforcing* them.

New defect found and fixed during the rework: the first MVP package hashes were computed from a Windows working tree with `core.autocrlf=true`. Git had rewritten the text (JCL) packages, for example NJE38 at 1,729,546 bytes on disk vs 1,696,693 in the blob. My first verification loop was also faulty (Python's CRLF output put `\r` in every expected hash) and reported 22 false mismatches. Corrected method: hashes and sizes come from `git cat-file blob HEAD:packages/<P>`, and are checked against fresh downloads from `raw.githubusercontent.com/MVS-sysgen/MVP/4c004a59…/packages/<P>` in `artifacts/cache/mvp-raw/` with `\r` stripped: **22/22 MATCH**. Consequence recorded for OSE-003 and OSE-013: caches must be fetched with `core.autocrlf=false`.

Commands (rework, Git Bash on Windows 11):
- `grep -n` over sysgen `jcl/{nje38,ispf,customize}.jcl` and `sysgen.py` for the MVP INSTALL calls: lines cited above.
- The `desc/` closure walk, `cache` lookup and rights scan (Python, cp037 for XMI): results in the lock entries and in the sysgen-pins addendum.
- `git cat-file blob` and sha256 for 22 packages, plus `curl -sSfL` from raw and sha256: 22/22 MATCH.
- `grep -i ufs370` over sysgen `*.py *.conf README.md jcl/` and MVP `cache`: no hits. ufsd README@1a63bf52 l.6, l.99, l.106 read.
- brexx370 README@5aabe493 l.123–132 read. Hercules `LICENSES/` listed at ee86c4de (5 files, not read).
- `python -I scripts/check_repo.py` and `python -I -m unittest discover -s tests/host`: results in the rework acceptance status below.

Rework acceptance status: (1) pass: 38 components, all 40-hex commits. (2) the reviewer's attempt-1 spot checks stand; the new mvp-pkg entries share the MVP commit, which the reviewer verified, and have content hashes verified 22/22. (3) pass, now including the MVP packages traced to sysgen JCL lines. (4) pass under the corrected rule: an SPDX value is given only where a license text was read at the pin (ufsd, ftpd, httpd, mvsmf, libc370, hercules-helper); everything else is UNRESOLVED with evidence. (5) pass: 9 release assets plus 22 MVP packages hashed from real downloads. **Gate: not met** until OSE-013 enforces the pins or the human amends the gate. *(Update 2026-11-26: the human amended the gate. Enforcement now belongs to OSE-013, and the MVP and RAKF pins are recorded under `pending_enforcement`, so the amended rule is met, pending re-review.)*

Next action: re-review by an independent agent (not this author). Human: approve OSE-013, choose between enforcing via OSE-013 and amending the gate, and answer licensing questions 1–9.

### Attempt 1 (superseded where Rework 1 differs; the "Known defects" claim about the escalation rule is withdrawn)
- Changed files / commits (uncommitted): `dependencies.lock.json` (16 components), `docs/research/2026-11-26-sysgen-pins.md`, `docs/research/2026-11-26-licensing.md`, `docs/adr/0005-pins-for-components-sysgen-does-not-pin.md` (Proposed), `upstream/sysgen/MANIFEST.md` (patch P-01 planned), corrections appended to `docs/research/2026-11-26-upstream-recon.md`, index updates.
- Commands run, RC, evidence paths (2026-11-26, Windows 11 Git Bash):
  - `git fetch --depth 1 https://github.com/MVS-sysgen/sysgen 4746195d…` and `…/MVS-sysgen/MVP 4c004a59…` into `artifacts/cache/{sysgen,MVP}`: RC 0.
  - URL and fetch grep over sysgen `*.py *.sh *.conf *.cnf Dockerfile*`: results in sysgen-pins P-1.
  - `git ls-remote` for every tag (peeled `^{}` where annotated): all resolved. SHAs are in the lock.
  - `curl -sSfL` of 9 release assets, then `sha256sum`: 9/9 MATCH `mvslovers.conf` (sysgen-pins P-3). Files in `artifacts/cache/assets/`.
  - License files fetched from raw.githubusercontent at each pinned SHA into `artifacts/cache/licenses/`. GitHub trees API used for repos without one.
  - `python -I scripts/check_repo.py` → OK, RC 0. `python -I -m unittest discover -s tests/host` → first run FAILED (1/10: `test_invalid_task_status` hard-coded `Status: READY` for this card). Fixed the test to rewrite any Status line, then re-ran → 10/10 OK, RC 0.
- Acceptance status: (1) pass: 16 components, all 40-hex commits. (2) existence shown by ls-remote/fetch for every entry; **the reviewer's 3-entry spot check is still to do**. (3) pass: every Sysgen-installed version traced to `mvslovers.conf` and sysgen.py lines. (4) pass: licenses read from files at the pin, unclear ones marked UNRESOLVED and listed for the human. (5) pass: 9 assets hashed from real downloads.
- Tests not run and why: the ufsd-utils linux-arm64 asset was not downloaded (no arm64 build host planned). The Hercules `LICENSES/` directory and the QPL conditions were not read in detail. The cc370 runtime GPL question is deferred to OSE-004.
- Decisions / ADRs: ADR-0005 proposed (toolchain matches the UFSD 1.5.2 build; Hercules 4.9.1; MVP pin via patch P-01).
- Known defects / blockers: MVP pin unenforceable without P-01 (escalation trigger "mutable fetch" → handled by proposing P-01, not blocking). RAKF pinned by tag only. README says RAKF v2.0.0 but the config says v2.1.0 (config wins). No license file in sysgen, MVP, sdsf or mbt; restrictive RAKF license → redistribution blocked pending the human.
- Next action: independent standard-tier review (re-run `git ls-remote` on 3 entries and re-hash 1 asset). Human: licensing questions 1–5 and ADR-0005. Then OSE-003 (needs ADR-0003 accepted).
- Usage/cost if available: not available to the agent (null in usage.jsonl).
## Independent review and gate result

### Gate result — VERIFIED (2026-11-26)
The independent reviewer confirmed that rework 2 fixes the re-review's circular-gate P2 (the OSE-013 completion boundary plus OSE-003 test 7). The human maintainer relayed the confirmation and directed VERIFIED, commit and merge. Original findings 1–3 were confirmed fixed in the re-review below. Accepted under the amended gate: pins are **recorded**, and the MVP and RAKF enforcement is still open in `pending_enforcement`, owned by OSE-013 and closed end to end by OSE-003 test 7. Licensing questions 1–9 stay with the human and do not block local M0 work.
### Re-review of Rework 1 — 2026-11-26
Independent reviewer, high tier (escalated after the previous failed review per tasks/README.md). Branch `task/OSE-002-rereview`, baseline `26dd7a6`; reviewed the uncommitted rework against that baseline, including the new OSE-013 card. **Original findings 1–3 addressed; OSE-002 remains BLOCKED, not VERIFIED. Changes requested on the new downstream gate sequencing below.**

- Finding 1: confirmed 22-package closure from pinned MVP `desc/*` starting at NJE38, ISPF, ISPTHEME and OPNTERSE, with no missing or extra lock entries. Independently compared all 22 versions with pinned MVP `cache`, all commits with the containing MVP pin, and all package SHA-256 values with both `git cat-file blob <pin>:packages/<name>` bytes and `artifacts/cache/mvp-raw/<name>`. All checks passed. UFS370 and docker-mvsce have explicit evidenced exclusions.
- Finding 2: confirmed ufsd-utils, BREXX, Hercules and cc370 are now UNRESOLVED; licensing addendum supersedes the original table and adds the open questions. This review makes no redistribution determination.
- Finding 3: confirmed BLOCKED status, both pending-enforcement entries, and explicit ownership in OSE-013; no claim that a proposed patch enforces a pin remains operative.

**New P2 — circular completion gate:** OSE-003 now depends on OSE-013, but OSE-013 acceptance test 5 requires the OSE-003 Sysgen run before OSE-013 can complete. OSE-002 is also held until OSE-013, while OSE-003 still depends on OSE-002. Under tasks/README.md's normal VERIFIED/MERGED dependency rule, no card can reach completion to unblock that run. The existing OSE-013 input exception (pins already recorded) permits host work, but does not resolve this later cycle. Define an explicit host-verified milestone that releases OSE-002/OSE-003, and assign end-to-end evidence to OSE-003, or split the enforcement and integration gates into acyclic stages. This is a task sequencing correction, not permission to remove pin verification.

Commands/results:
- `python -I scripts/check_repo.py`: RC 0, `check_repo: OK`.
- `python -I -m unittest discover -s tests/host`: RC 0, 11 tests, OK (outside sandbox because its AGENTS.md fixture copies require it).
- `python -I -` inline read-only audit using `subprocess.check_output(['git','-C','artifacts/cache/MVP','cat-file','blob',pin+':'+path])`, a Depends closure walk, pinned `cache` lookup, and `hashlib.sha256` on blobs and cached raw files: RC 0, closure 22, missing `[]`, extra `[]`, all 22 hash/version/commit checks PASS. An initial reviewer audit attempt failed because its regex used `\s*` after an empty Depends field and consumed the next line; corrected to `[ \t]*` before the successful run. No product code changed.

Limits: the 22 raw files were already cached; no new network downloads were performed in this re-review. Prior review's three remote tag checks and release-asset spot check stand. No guest execution. Only this review record and usage log changed by the reviewer. Next action: reconcile the new task's completion sequence, then implement and independently verify pin enforcement; retain BLOCKED status until its gate is satisfied or explicitly amended by the human.

### Initial review (historical)
2026-11-26 — independent reviewer, standard review scope. **CHANGES REQUESTED; not VERIFIED.** Review branch: `task/OSE-002-review`. Baseline: unborn repository; all bootstrap files are untracked, so no commit diff was available. This review checked the current files and cached pinned sources, not authorship of individual edits. No guest work or legal conclusions.

Findings:
1. **P1 — incomplete component inventory.** The goal includes every component installed by pinned Sysgen. `sysgen.py` calls `jcl/nje38.jcl`, `jcl/ispf.jcl` and `jcl/customize.jcl`; those install NJE38, ISPF, ISPTHEME and OPNTERSE via MVP. They have no component-level version/license records in the lock; a single MVP entry with unresolved licensing does not inventory those third-party packages. At pinned MVP, `cache` lists NJE38 2.3.0, ISPF 2.2.0 and OPNTERSE 0.1.2. Inventory their dependency closure and rights evidence using the containing repo commit where appropriate. UFS370, explicitly named in this card's inputs, is also absent: record its pin/license or an evidenced exclusion.
2. **P2 — license acceptance is overstated.** `dependencies.lock.json` assigns ufsd-utils `license_spdx: MIT` while its evidence is only a README declaration and explicitly says there is no license text. This fails acceptance test 4 and accepted ADR-0004 item 6; use UNRESOLVED until qualifying evidence is read. BREXX also explicitly leaves GPL only/or-later undetermined but presents a resolved SPDX value. Hercules is marked redistribution permitted while `LICENSES/` and conditions remain unread. Keep incomplete conclusions unresolved and add the outstanding Hercules review to the human questions rather than marking license acceptance passed.
3. **P2 — mutable-fetch gate bypass.** The handoff says MVP's pin is unenforceable and explicitly handles the mutable-fetch escalation by proposing P-01 instead of blocking. A planned patch owned by OSE-003 does not enforce the recorded pin or amend this card's escalation rule. Record the blocked pin-enforcement prerequisite and its owner, or obtain an explicit scope/gate amendment; do not claim the gate is satisfied by the proposal alone.

Verification commands and results (PowerShell, 2026-11-26):
- `python -I scripts/check_repo.py`: output `check_repo: OK`, RC 0.
- `python -I -m unittest discover -s tests/host`: sandbox run RC 1, 10 setup errors copying `AGENTS.md` into temporary directories (PermissionError). Retrying with a workspace-local temporary directory had the same result. Exact original command rerun outside the sandbox: `Ran 10 tests ... OK`, RC 0. No test code changed.
- `git ls-remote https://github.com/mvslovers/ufsd refs/tags/v1.5.2`: RC 0, `1a63bf52fe51a276757b9062aa4072cb17a62762 refs/tags/v1.5.2`.
- `git ls-remote https://github.com/mvslovers/RAKF refs/tags/v2.1.0`: RC 0, `941b07dc19adb7a1a153caaeba96b659ff2ad3e0 refs/tags/v2.1.0`.
- `git ls-remote https://github.com/mvslovers/libc370 'refs/tags/v2.25.1*'`: RC 0, tag object `82016ba568e8f69260a795d29fc210f8e21cb856`, peeled commit `fcde4e88b3bebca001355aa3c1dd3c3a633f04af`. All three commits match the lock. Initial sandbox network attempts each failed with RC 128 (proxy connection refused); successful checks ran outside the sandbox.
- `Get-FileHash artifacts/cache/assets/ufsd-1.5.2-dist.tar.gz -Algorithm SHA256`: RC 0; `4d3f656a91403e8b356d665e41839f13a20b375599d8c1c71062d073b1da3218`, matches lock and cached pinned `mvslovers.conf`.
- `git -C artifacts/cache/sysgen rev-parse HEAD` and `git -C artifacts/cache/MVP rev-parse HEAD`: RC 0; match the full sysgen and MVP commits in the lock.

Limits: only the required three remote entries and one cached asset were independently spot-checked; remaining remote pins and downloads were not reverified. Next action: author addresses findings, records revised acceptance evidence, and requests re-review; failed-review routing follows tasks/README.md. Human retains licensing decisions and merges.

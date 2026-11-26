# CC/370 toolchain on the host (OSE-004, host part)

- Task: OSE-004. Date: 2026-11-26. Platform: Windows 11 workstation, with Docker Desktop 29.9.3 running the ADR-0003 option A container (`debian@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e`, linux/amd64, non-root uid 1000). No guest exists yet, so nothing here ran on MVS.
- Pins: cc370 v1.6.3 `802dde1c`, libc370 v2.25.1 `fcde4e88`, mbt v3.0.1 `83fdb876` (lock). maclib370 v1.0.0 `e85286a7` was examined but is **not approved** (T-1).
- Evidence lives under `artifacts/evidence/ose-004/` (git-ignored). Reproduce with `scripts/build.sh` (runbook: [hello-compile-deploy.md](../runbooks/hello-compile-deploy.md)).
- Confidence labels per ADR-0002.

## T-1 Blocker: maclib370 is a required dependency that is not in the lock

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 1.1 | `libc370` 2.25.1 refuses to build without maclib370: `maclib370 not found: install it beside cc370 (<sysroot>/maclib370/macros) or set MACLIB370 … (#494)`, make RC 2. | `artifacts/evidence/ose-004/libc370-build-without-maclib370.txt` | observed |
| 1.2 | Since libc370 2.8.0 the IBM `SYS1.MACLIB`/`SYS1.AMODGEN` members come from maclib370, and libc370 no longer vendors them. The accepted range is `>= 1.0.0, < 2`. | `libc370:CHANGELOG.md:1198-1215`; `libc370:sdk/maclib370.json` | documented |
| 1.3 | cc370 after 1.5.0 depends on maclib370 (>= 1.0.0), and `as370` searches `<exedir>/../maclib370/macros`. | `cc370:README.md:84-85, 157-160` | documented |
| 1.4 | maclib370 v1.0.0 = `e85286a7cb994eae4003143eba693ab7931b026e`, the only tag. It holds 747 SYS1.MACLIB and 288 SYS1.AMODGEN members, **taken from a TK5 system (Update 5), not from MVS/CE**, including TK5 usermods. Ten members differ from the IBM distribution level, among them `GETMAIN` (ZP60033, adds `LOC=`), `WTO`, `WTOR`, `GTTERM`, `STFSMODE`, `IKTTCAST` and `IEAPMNIP`. | `maclib370:README.md:1-60` | documented |
| 1.5 | maclib370's `LICENSE` (MIT) covers only its tools, manifest and README. The IBM macros are explicitly **not** covered: "This repository records where they came from; it makes no statement about them beyond that." | `maclib370:README.md` "Origin and licenses"; `maclib370:LICENSE` | documented |
| 1.6 | The OSE-002 inventory missed this dependency, so the lock is incomplete for the toolchain. | `dependencies.lock.json` (no maclib370 entry) | observed |

Consequences:
- Without approval OSE cannot build `libc.a`, and so cannot link any C program. Compiling and assembling user code still works (T-3).
- **Compatibility hazard (hypothesis):** assembling MVS/CE programs against TK5 macros can generate code that MVS/CE lacks the PTF or usermod for, `GETMAIN LOC=` being the clearest case. libc370 itself chose these macros, so the risk applies to every libc370 build in the ecosystem. OSE-006 or a guest test must show that a libc370 built this way runs on the pinned MVS/CE.
- **Licensing:** this adds IBM macro text with no stated rights to the open questions in research 2026-11-26-licensing.

The human has to choose (recorded in the OSE-004 card):
- **(a)** Approve maclib370 v1.0.0 `e85286a7` as a lock entry (`license_spdx` UNRESOLVED for the macro content). This is the upstream-supported path.
- **(b)** Build a macro tree from the pinned MVS/CE image instead: our IBM distribution tape (AMACLIB and ATSOMAC, research 2026-11-26-tso-terminal-audit) or the OSE-003 guest's `SYS1.MACLIB`, using maclib370's own `tools/extract.py --unloaded`. This matches the target system better but needs OSE-003 and more work.
- **(c)** Use the prebuilt libc370 2.25.1 sysroot release asset. This avoids building libc370, but the asset would need a lock entry and a hash, and it still embeds code assembled against maclib370.

## T-2 Toolchain build (observed)

| Item | Value |
|---|---|
| Command | `sh scripts/build.sh toolchain` → RC 0 |
| Image packages | `gcc=4:12.2.0-3`, `libc6-dev=2.36-9+deb12u14`, `make=4.3-4.1`, `python3=3.11.2-1+b1`, `flex=2.6.4-8.2`, `bison=2:3.8.2+dfsg-1+b1`, `git=1:2.39.5-0+deb12u3` (`artifacts/evidence/ose-004/apt-versions.txt`). Installed from the live Debian mirror and not pinned by snapshot, so a rebuild may get newer patch levels. |
| Version strings | `cc370 1.6.3 (802dde1), based on GCC 3.4.6`; `as370 1.6.3 (802dde1)`; `ld370 1.6.3 (802dde1)` (`versions.txt`) |
| Targets used | `make tools compiler`, then `install-tools install-compiler install-macros` with `PREFIX=artifacts/toolchain` (the `runtime` and `man` targets are skipped) |
| Build time | about 2 min |
| Findings | (1) The GCC 3.4.6 build needs **flex and bison**: the first attempt failed on `gengtype-lex.c`/`gengtype-yacc.c` being missing. The README does not list them. (2) Without `git` in the image the version string reads `(unknown)`, because `common/mkversion.sh` derives the commit from git. (3) On the Windows bind mount, installed binaries do not show the executable bit from the host side, so the scripts test `-f`, not `-x`. |

## T-3 hello: compile and assemble (observed), link blocked

- Source: `src/utils/hello/hello.c`. It prints `OSE-004 HELLO RC=<n>` and returns `atoi(argv[1])` (0 without PARM).
- `cc370 -S -O1` → RC 0, and `cc370 -c -O1` → RC 0. as370 needs only cc370's own `pdptop.copy`, `pdpprlg.macro` and `pdpepil.macro`. `pdpprlg` writes out what `SAVE (14,12),,ID` generates, so no IBM macro is needed (`artifacts/toolchain/cc370/macros/pdpprlg.macro:26-29`). Before `install-macros` the assembly failed with `COPY member PDPTOP not found (IFO068)`.
- sha256: `hello.s` `866cd3026ea6aa6b658ad8352ae15658f25f28086239371ac2ad83ec944bb55c`, `hello.o` `c3a870f9cf30bd9b672a793eb41ebe833a1afc4b8b8637273761a365843a1872`. **Two separate toolchain builds produced the same `hello.o` bytes.** The object holds `CC370` + version bytes but no commit hash.
- `file370`: OS/360 object deck, 9 cards. One private-code section of 0xC4 bytes. Entries `@@MAIN` (+0x20) and `MAIN` (+0x2C). Externals `@@CRT0`, `ATOI` and `PRINTF`. END entry at +0x20.
- `scripts/build.sh hello` exits **3** at the link step: there is no `libc.a` (T-1). The load module, its sha256 and acceptance tests 1–4 are therefore open.

## T-4 C dialect (observed at compile time, not run)

The OSE-012 probes were compiled with `cc370 -S -O1` against the libc370 2.25.1 headers (`artifacts/evidence/ose-004/probes/summary.txt`, `probes-extra/summary.txt`).

| Probe | Construct | Result |
|---|---|---|
| p01 | `long long` arithmetic | RC 0 |
| p02 | `//` comments (default mode) | RC 0 |
| p03 | designated initializers | RC 0 |
| p04 | variadic macros `__VA_ARGS__` | RC 1 for the OSE-012 file, because of a **probe defect**: the file has a raw newline inside a string literal where `\n` was meant. A corrected copy (`probes-extra/p04_fixed.c`) gives RC 0. The fix belongs on the OSE-012 branch. |
| p05 | `static inline` | RC 0 |
| p06 | `<stdint.h>` `uint8_t`/`uint16_t`/`uint32_t`/`int32_t` and `sizeof(void *) == 4` | RC 0 (compile-time size asserts hold) |
| p07 | `struct hdr` of 12 bytes with offsets 2 and 4, and `__attribute__((packed))` giving size 5 | RC 0 (compile-time asserts hold) |
| p08 | mixed declarations and `for (int i…)` | RC 1 in the default mode ("'for' loop initial declaration used outside C99 mode"), RC 0 with `-std=c99` and with `-std=gnu99` |

Predefined macros: `__CC370__ 10603`, `__GNUC__ 3`, `__MVS__ 1`, `__CHAR_UNSIGNED__ 1` (**plain `char` is unsigned**). The default language mode is GNU89; C99 is available with `-std=`.

These are compile-time facts only. Runtime behaviour, such as `long long` division (cc370 notes a past `__divdi3` miscompile, now fixed) and the packed-struct access code, needs a guest run.

The spec §3.2 constructs (fixed-width types and explicit packing) are available, so the OSE-012 escalation trigger to OSE-010 does **not** fire.

## T-5 Linkage and output (from the generated assembler; documented or observed as marked)

| Item | Finding | Confidence |
|---|---|---|
| Entry | `@@MAIN` stub loads `=V(@@CRT0)` and branches. `main` is an LD entry with prologue `PDPPRLG CINDEX=0,FRAME=96,BASER=12,ENTRY=YES` and epilogue `PDPEPIL`. | observed (`hello.s`) |
| Calls | OS linkage: R1 → argument list, `L 15,=V(name)`, `BALR 14,15`, result in R15. `main`'s return value is placed in R15 before `PDPEPIL`. | observed (`hello.s`) |
| Character set | String literals are emitted as CP037 `C'…'`, and **`\n` becomes X'15' (NEL)**, the mvslovers ecosystem convention, not CP037 LF X'25'. | observed (`hello.s`: `DC X'15'`); rationale documented in the cc370 repo notes |
| AMODE/RMODE, RENT/REUS | Set at link (`ld370 --rent/--reus/--refr`; the default since cc370#100 is neither) and not visible in the object deck. Open until a link. | documented (cc370 repo notes) |
| Code page for host sources | cc370 reads UTF-8 or Latin-1 sources and maps narrow strings to CP037. | documented (cc370 repo notes) |

## T-6 Deploy transport (documented, from mbt source)

- `mbt deploy` (v3.0.1) uses **mvsMF**, a z/OSMF-style REST API, at `http://{host}:{port}/zosmf` with **HTTP Basic** authentication. That means plain HTTP: credentials are only base64-encoded on the wire. Defaults are host `localhost`, port `1080`, user `IBMUSER`, and the password comes from the environment or config (`mbt:scripts/mbt/mvsmf.py:6-7, 86, 120`; `scripts/mbt/config.py:22-32`).
- Flow: pack the modules into one XMIT, upload it to `{HLQ}.MBT.XMIT.IN`, delete the target LINKLIB, then submit a TSO RECEIVE job and read its spool through the REST job API (`mbt:scripts/mbtdeploy.py:1-38`).
- For OSE-007: deployment requires a **running mvsMF**, which research 2026-11-26-ufsd-audit G-12 and recon R-03 list as an alternate access path to guest data. A deploy path that avoids mvsMF, such as a Hercules card-reader submit of RECV370 JCL plus an XMIT on a tape or reader, should be evaluated before mvsMF is enabled. `make deploy` is not written yet: it needs both a guest and this decision.

# UFSD interface as observed at v1.5.2

- Kind: **observed upstream interface** (evidence, not an OSE contract; see [README](README.md)).
- Source: mvslovers/ufsd `1a63bf52fe51a276757b9062aa4072cb17a62762` (v1.5.2). Read 2026-11-26 by OSE-005, static reading only. Offsets are computed from the C declarations for S/370 (4-byte `int`, `unsigned` and pointers, big-endian) and are **not yet confirmed by a dump**. OSE-006 should confirm them on the guest.
- Findings and the gap list: [docs/research/2026-11-26-ufsd-audit.md](../research/2026-11-26-ufsd-audit.md).

## 1. Transport

| Item | Value | Source |
|---|---|---|
| Subsystem name | `UFS1` (STC jobname stays `UFSD`) | `include/ufsd.h:562` |
| SSOB function code | 128 (`UFSD_SSOBFUNC`), SSVT router index 1 | `include/ufsd.h:541-542` |
| Client call | libc370 `iefssreq(&ssob)`: requires APF or supervisor state, `MODESET MODE=SUP`, branch to `JESCT+20` | `client/libufs.c:58-85`; `libc370@fcde4e88:src/mvs/subsys/iefssreq.c:5-32` |
| Router | `UFSDSSIR`, in CSA SP 241, runs in the client address space; switches to key 0 with `__super` (requires APF) | `src/ufsd#ssi.c:93-156` |
| Router → server | CS-push of a `UFSREQ` onto `anchor->req_head`; `__xmpost` of `anchor->server_ecb` if the queue was empty | `src/ufsd#ssi.c:221-231` |
| Server → router | `__xmpost(req->client_ascb, req->client_ecb_ptr, 0)` | `src/ufsd#que.c:288` |
| Client wait | `ecb_timed_wait` in 5 s slices; after each slice the eye catcher and ACTIVE are re-checked; no overall timeout | `src/ufsd#ssi.c:49-57, 248-288` |
| Anchor lookup | `ssct_find("UFS1")->ssctsuse`, eye `UFSDANCR`, layout `version` 2 | `src/ufsd#ssi.c:125-138`; `include/ufsd.h:276-280` |

Result reporting: `SSOBRETN` gets the router's refusal code or the server rc. `UFSSSOB.rc` gets the server rc. libufs folds a router refusal into `rc` (`client/libufs.c:79-83`). R15 ≠ 0 from `iefssreq` means the request did not reach UFSD, and libufs returns -1.

## 2. `UFSSSOB` (client ↔ router, client storage)

| Off | Len | Field | Notes |
|---|---|---|---|
| 0 | 4 | `eye` | `"UFSS"` |
| 4 | 4 | `func` | `UFSREQ_*`, §3 |
| 8 | 4 | `token` | session token; 0 = none |
| 12 | 4 | `rc` | output; must be at +12 (`iefssreq` convention, `include/ufsd.h:573-578`) |
| 16 | 4 | `errno_val` | output; **always 0** (`src/ufsd#que.c:222`) |
| 20 | 4 | `data_len` | 0–256; the router clamps to 256 |
| 24 | 256 | `data` | inline parameters / result |
| 280 | 4 | `client_ecb` | declared; no code at the pin reads it (the router waits on its own stack ECB, `src/ufsd#ssi.c:104, 173-174`) |
| 284 | 4 | `buf_ptr` | **raw client address**, read (FWRITE) or written (FREAD) by the router in key 0 without validation (`src/ufsd#ssi.c:199-213, 307-316`) |
| 288 | 4 | `buf_len` | capacity of `buf_ptr` |

Size 292 bytes. Source: `include/ufsd.h:564-584`. There is no version, no total length, no flags and no correlation ID.

## 3. Function codes and payloads

From `include/ufsd.h:377-397`, `src/ufsd#fil.c:19-35`, `client/libufs.c:9-28` and `src/ufsd#que.c:156-211`. Offsets are within `data[]`. "Session" means `ufsd_sess_find(token)` must succeed (`src/ufsd#que.c:175, 198`).

| Code | Name | Session | Request `data` | Response `data` |
|---|---|---|---|---|
| 0x01 | PING | no | — | — |
| 0x10 | SESS_OPEN | no | optional [0..8] owner, [9..17] group (used only if `data_len` ≥ 18; `src/ufsd#ses.c:231-236`) | [0..3] token |
| 0x11 | SESS_CLOSE | yes | — | — |
| 0x12 | SETUSER | yes | [0..8] userid NUL-terminated, [9..17] group or zeros = keep; `data_len` must be 18 | — |
| 0x20 | FOPEN | yes | [0..3] mode (1 = READ, 2 = WRITE create/truncate), [4..] path NUL-terminated | [0..3] fd |
| 0x21 | FCLOSE | yes | [0..3] fd | — |
| 0x22 | FREAD | yes | [0..3] fd, [4..7] count | [0..3] bytes read, [4..] data inline (≤ 252); or data via 4K buffer → `buf_ptr` |
| 0x23 | FWRITE | yes | [0..3] fd, [4..7] count, [8..] data inline (≤ 248); or data from `buf_ptr` via 4K buffer | [0..3] bytes written |
| 0x24 | FSEEK | — | reserved; falls to `default` → `UFSD_RC_NOTIMPL` (24) | — |
| 0x30 | MKDIR | yes | [0..] path | — |
| 0x31 | CHGDIR | yes | [0..] path | — |
| 0x32 | RMDIR | yes | [0..] path | — |
| 0x33 | REMOVE | yes | [0..] path | — |
| 0x40 | DIROPEN | yes | [0..] path | [0..3] dir fd |
| 0x41 | DIRREAD | yes | [0..3] dir fd | 98-byte entry, below; ino = 0 means end |
| 0x42 | DIRCLOSE | yes | [0..3] dir fd | — |
| 0x50 | GETCWD | yes | — | [0..] path NUL-terminated |
| 0x60 | STAT | yes | [0..] path | 98-byte entry, below |

DIRREAD and STAT entry (`include/ufsd.h:506-516`): [0..3] ino, [4..7] size, [8..9] mode, [10..11] nlink, [12..71] name (60), [72..79] mtime (ms since the epoch, 64-bit), [80..88] owner (9), [89..97] group (9).

Codes from 0x01 to 0xFF that are not listed return `UFSD_RC_NOTIMPL`. Codes outside that range return `UFSD_RC_BADFUNC` (`src/ufsd#que.c:124-136, 208-210`).

## 4. libufs public API

These are the 38 declarations in `include/libufs.h:176-244`. The `asm()` names match ufs370 NCALIB members, so ufs370 programs relink unchanged (`include/libufs.h:167-173`). The status column feeds the OSE-012 compatibility table.

| Function | Alias | Server call | Observed behaviour |
|---|---|---|---|
| `ufsnew` / `ufsfree` | — | SESS_OPEN / SESS_CLOSE | session with an empty owner |
| `ufs_sys_new` / `ufs_sys_term` | UFSSYNEW / UFSSYTRM | none | stubs |
| `ufs_get_sys` / `ufs_set_sys` | UFS#GSYS / UFS#SSYS | none | handle fields |
| `ufs_get_cwd` / `ufs_set_cwd` | UFS#GCWD / UFS#SCWD | none | client-side copy of the cwd |
| `ufs_get_acee` / `ufs_set_acee` | UFS#GACE / UFS#SACE | none | pointer stored client-side, never sent |
| `ufs_get_create_perm` / `ufs_set_create_perm` | UFS#GCRE / UFS#SCRE | none | never sent; the server always uses 0644 and 0755 |
| `ufs_signon` / `ufs_signoff` | UFS#SON / UFS#SOFF | none | stubs, always succeed (`client/libufs.c:316-330`) |
| `ufs_setuser` | UFS#SUSR | SETUSER | **unverified identity change** |
| `ufs_last_rc` | UFS#GLRC | none | last stored rc |
| `ufs_chgdir`, `ufs_mkdir`, `ufs_rmdir`, `ufs_remove` | UFS#CD, UFS#MD, UFS#RD, UFS#REM | CHGDIR, MKDIR, RMDIR, REMOVE | path < 256 characters |
| `ufs_diropen`, `ufs_dirread`, `ufs_dirclose` | UFS#DOPN, UFS#DRD, UFS#DCLS | DIROPEN, DIRREAD, DIRCLOSE | reads the whole directory at open into a sorted array; `pattern` ignored |
| `ufs_fopen`, `ufs_fclose` | UFS#FOPN, UFS#FCLS | FOPEN, FCLOSE | mode `r`/`R` = read; **everything else = write + truncate** |
| `ufs_fsync`, `ufs_sync` | UFS#FSYN, UFS#SYNC | FWRITE / none | flushes the client buffer / no-op |
| `ufs_fread`, `ufs_fwrite` | UFS#FRD, UFS#FWT | FREAD, FWRITE | chunked at 252/248 bytes inline or 4096 bytes via buffer |
| `ufs_fgets`, `ufs_fputc`, `ufs_fputs`, `ufs_fgetc` | UFS#FGTS, UFS#FPTC, UFS#FPTS, UFS#FGTC | via fread/fwrite | 4K read-ahead and write-behind per handle |
| `ufs_stat` | UFS#STAT | STAT | |
| `ufs_fseek` | UFS#FSEE | none | **always returns -1** (`client/libufs.c:1137-1144`) |
| `ufs_feof`, `ufs_ferror`, `ufs_clearerr` | UFS#FEOF, UFS#FERR, UFS#CERR | none | handle flags |

There is no rename, link, symlink, chmod, chown, utime, truncate, access, dup or getcwd-from-server function in libufs. (GETCWD exists on the wire, but libufs keeps the cwd locally.)

## 5. Return codes

`include/ufsdrc.h:10-28`: 0 OK, 4 NOREQ (pool or table full), 8 CORRUPT (router refusal or server gone), 12 BADFUNC, 16 BADSESS, 20 INVALID, 24 NOTIMPL, 28 NOFILE, 32 EXIST, 36 NOTDIR, 40 ISDIR, 44 NOSPACE, 48 NOINODES, 52 IO, 56 BADFD, 60 NOTEMPTY, 64 NAMETOOLONG, 68 ROFS, 72 EACCES. libufs returns -1 when the SSI call failed.

## 6. Limits

See audit U-7.3 and `docs/books/ref/ref-lim.typ:12-68`.

| Item | Limit |
|---|---|
| Mounts | 16 |
| Sessions | 64 |
| fds per session | 64 |
| Open files in total | 256 |
| CSA request blocks | 32 |
| 4K buffers | 16 |
| Inline payload | 256 bytes |
| Path | 255 characters (`fopen` 251) |
| Name | 59 characters |
| File size | `(16 + b/4) × b` |

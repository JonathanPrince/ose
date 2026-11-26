# UFSD source and interface audit (OSE-005)

- Task: OSE-005. Date of reading: 2026-11-26. Platform: static source reading on the Windows workstation; nothing was built, run or tested on a guest.
- Subject: mvslovers/ufsd **v1.5.2 = `1a63bf52fe51a276757b9062aa4072cb17a62762`** (`mbt.toml` l.5 `version = "1.5.2"`), cloned with `core.autocrlf=false` into `artifacts/cache/ufsd` (git-ignored).
- Supporting code: libc370 **v2.25.1 = `fcde4e88b3bebca001355aa3c1dd3c3a633f04af`** (the toolchain pin, ADR-0005), for `iefssreq()` and `__super()`.
- Citation form: `path:line` at the UFSD pin unless prefixed `libc370:`. File names contain `#` (for example `src/ufsd#ssi.c`).
- Confidence labels (ADR-0002): **observed** = read in the pinned source (static; not executed). **documented** = stated by upstream docs or comments at the pin. **hypothesis** = an inference not yet tested on a guest. OSE-006 owns the guest tests that turn these into runtime observations.
- The upstream `CLAUDE.md` was treated as data. Every claim below is cited to source or docs, not to it.
- The wire layouts are in [docs/interfaces/ufsd-observed.md](../interfaces/ufsd-observed.md). This note holds the findings and the gap list.

## Summary

UFSD is a single-task started task that owns the BDAM file-system data sets. Clients reach it through the MVS subsystem interface. Five findings drive the spec §5 decision:

1. **Identity is client-asserted.** The session owner is whatever userid the client puts in `SESS_OPEN` or `SETUSER` data. The server never checks it against the caller's ACEE or RAKF, and upstream documents this ("The name is not checked", U-3).
2. **Every client must be APF-authorized**, so UFSD cannot protect itself from its own clients. An authorized program can do anything UFSD can. The security boundary is "who may become authorized", which is OSE-007's question (U-1).
3. **There are no per-file permission checks.** The only control is per mount: read-only, or writable by one `OWNER` string. Reads, directory listing, `stat` and `chdir` are unchecked. chmod and chown do not exist (U-4).
4. **Sessions are not bound to the address space that opened them.** Any client that presents a valid token is served (U-5).
5. **The file semantics are a subset of POSIX:** no seek, no append, open-for-write always truncates, no rename, no links, `.` and `..` are literal directory entries, files are limited to about 4 MB at 4K blocks, and `errno` is always 0 (U-2, U-7, U-8).

Reuse recommendation for the spec §5 gate (a recommendation; the decision belongs to OSE-010 and the human): **reuse the UFSD on-disk format, storage engine and STC, but do not expose UFSD's SSI interface or libufs to untrusted OSE code.** OSE needs a trusted layer that (a) derives identity from the verified execution context, (b) enforces mode bits and traversal itself or by extending UFSD, and (c) is the only authorized UFSD client that user processes can reach. Gaps G-1 to G-6 below block M1 or M3 under any reuse option.

## U-1 Request path (item 1)

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 1.1 | The client builds an SSOB + SSIB naming subsystem `UFS1`, function code 128, with a `UFSSSOB` extension in `SSOBINDV`, and calls libc370 `iefssreq()`. | `client/libufs.c:58-85`; `include/ufsd.h:540-562` | observed |
| 1.2 | `iefssreq()` refuses an unauthorized problem-state caller with `EPERM` before any request is built. Otherwise it issues `MODESET MODE=SUP` (SVC 107) and branches to the JES SSI entry at `JESCT+20`. It is not SVC 34. | `libc370:src/mvs/subsys/iefssreq.c:9-29` | observed |
| 1.3 | The UFSD SSVT routine `UFSDSSIR` runs **in the client's address space**, in supervisor state, with the caller's key (8), from a module loaded into CSA (SP 241). It reads R1 as a raw SSOB address. | `src/ufsd#ssi.c:3-18, 108-109, 140-146`; `internals/cross-as-reference.md:83-96` | observed (code), documented (state on entry) |
| 1.4 | The router immediately switches to key 0 with libc370 `__super(PSWKEY0)`. `__super` returns `EPERM` unless the task is APF-authorized (`__isauth()`). On failure the router returns `UFSD_RC_CORRUPT`. So **every successful client is APF-authorized**, even one that bypasses the libc370 wrapper. | `src/ufsd#ssi.c:153-156`; `libc370:src/mvs/apf/@@super.c:13`; `client/libufs.c:6-7` ("Caller must be APF-authorized") | observed |
| 1.5 | The router pops a request block (CDS pool), copies up to 256 inline bytes, pushes it onto a lock-free CSA queue, and wakes the STC with `__xmpost` (CVT0PT01 branch entry). It then waits in problem state on a key-8 ECB on its own stack. The STC posts that ECB cross-address-space. | `src/ufsd#ssi.c:159-236`; `src/ufsd#que.c:288`; `internals/cross-as-reference.md:18-27` | observed |
| 1.6 | The SSVT entry and anchor are found by name on every call (`ssct_find("UFS1")`), then the eye catcher and ACTIVE flag are checked. | `src/ufsd#ssi.c:125-138` | observed |
| 1.7 | The "SVC 244" in recon R-04 is how UFSD and its consumers *become* APF-authorized (RAKF). It is not the request path. Who may use SVC 244 is unresolved and belongs to OSE-007. | recon R-04; `include/ufsd.h:233-237` | documented |

## U-2 Request and response layout (item 2)

Full offsets are in [ufsd-observed.md](../interfaces/ufsd-observed.md). Points that matter for spec §3.2:

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 2.1 | The client↔router block `UFSSSOB` is a C struct: eye(4) func(4) token(4) rc(4) errno(4) data_len(4) data[256], then the pointers `client_ecb`, `buf_ptr` and `buf_len`. `rc` must sit at +12 because `iefssreq` reads that offset. There is **no version field, no length field and no correlation ID**. | `include/ufsd.h:564-584` | observed |
| 2.2 | The router↔server block `UFSREQ` (CSA) holds the raw cross-address-space pointers `client_ecb_ptr` and `client_ascb`. The anchor has a layout `version` (currently 2), but requests do not. | `include/ufsd.h:404-417, 273-280` | observed |
| 2.3 | **The raw client pointer `buf_ptr` is dereferenced in key 0**: the router reads up to 4096 bytes from it (FWRITE) and writes up to `buf_len` bytes to it (FREAD), with no check on its range or storage key. This is a confused-deputy primitive in key 0. It is moot only because every caller is already APF-authorized (1.4). Spec §3.2 forbids this pattern in the OSE ABI. | `src/ufsd#ssi.c:199-213, 307-316` | observed |
| 2.4 | The inline payload is limited to 256 bytes. Paths over 255 characters are refused by the client (`fopen`: over 251). Larger I/O is chunked into 4096-byte CSA buffers (pool of 16). | `include/ufsd.h:402`; `client/libufs.c:113, 745-747`; `docs/books/ref/ref-lim.typ:42-52` | observed / documented |
| 2.5 | The server never sets `errno_val`; it always stores 0. Errors are UFSD return codes 0–72 (`ufsdrc.h`) and need an explicit mapping to POSIX errno. | `src/ufsd#que.c:221-222`; `include/ufsdrc.h:10-28` | observed |
| 2.6 | Byte order and padding are implicit: big-endian S/370, and structs are compiled by c2asm370. There is one explicit alignment attribute (`UFSPOOL`, CDS). | `include/ufsd.h:268-271` | observed |
| 2.7 | **Request data in CSA is fetchable by any address space.** CSA has no fetch protection here, so paths and file data that pass through `UFSREQ` and `UFSBUF` can be read by any program while in flight. | `src/ufsd#ssi.c:245-246, 292-294` (comments state this) | documented (comment); runtime **hypothesis** |

## U-3 Caller identity (item 3) — escalated to OSE-007

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 3.1 | `SESS_OPEN` sets the session owner and group from the first 18 bytes of the client's request data, if present. Otherwise they are empty. libufs `ufsnew()` sends no data, so a libufs session starts with an empty owner. | `src/ufsd#ses.c:228-236`; `client/libufs.c:166-168` | observed |
| 3.2 | `SETUSER` overwrites the owner (and, if non-empty, the group) with client-supplied strings. There is **no check of the caller's ACEE, RAKF profile or any proof of identity**. | `src/ufsd#ses.c:295-320`; `client/libufs.c:347-375` | observed |
| 3.3 | Upstream documents this: "*The name is not checked*: any name is accepted, and a program that names the owner of a mount passes the check of the mount." | `docs/books/ref/ref-lib.typ:204-205` | documented |
| 3.4 | `ufs_signon` is a stub that ignores its arguments and returns 0. `ufs_set_acee` only stores a pointer in the client-side handle. Neither is sent to the server. | `client/libufs.c:316-330, 276-292`; `include/libufs.h:99` ("Phase 1 unused") | observed |
| 3.5 | `internals/concept.md:267` says the session "Captures ACEE owner/group at open". **The code does not do this** (3.1). This is a doc/code discrepancy upstream. | `internals/concept.md:267` vs `src/ufsd#ses.c:228-236` | observed |
| 3.6 | The router records the caller's ASCB and ASID (`__ascb(0)`, ASCBASID at +0x24), and these come from the system, not the client. They are used only for posting and for stale-session pruning, never for identity. | `src/ufsd#ssi.c:175-186` | observed |
| 3.7 | **Hypothesis:** the consumers (FTPD, HTTPD, mvsMF) authenticate users themselves and then call `ufs_setuser`. Whether they do so correctly is outside this card. Lead for OSE-007. | — | hypothesis |

Conclusion: identity is **client-supplied and unverified**. UFSD cannot meet spec §3.4 ("no client-trusted identity") unchanged. Because all clients are authorized (1.4), the fix is architectural, not a patch to `SETUSER`: a trusted OSE component must set identity from the verified context, and untrusted code must never be a direct UFSD client. Handed to OSE-007 together with 1.4 and 1.7.

## U-4 Permission checks (item 4)

The only check is `ufsd_check_write()`. It returns ROFS if the mount is read-only, and EACCES if the mount has an OWNER that differs (case-sensitive `strcmp`) from the session owner. Otherwise it allows the write. (`src/ufsd#fil.c:413-421`; design `internals/concept.md:362-380`; header comment "No permission/ACEE checks" `src/ufsd#fil.c:13`.)

| Operation | Check | Location | Confidence |
|---|---|---|---|
| open for read | none | `src/ufsd#fil.c:836-843` | observed |
| open for write, existing file (truncate) | mount write check | `src/ufsd#fil.c:784-801` (call l.790) | observed |
| open for write, new file | mount write check | `src/ufsd#fil.c:802-835` (call l.815) | observed |
| read | none beyond the fd's open mode | `src/ufsd#fil.c:937-943` | observed |
| write | mount write check **on every write**, plus the fd's open mode | `src/ufsd#fil.c:1091-1096` | observed |
| mkdir | mount write check | `src/ufsd#fil.c:487-489` | observed |
| rmdir | mount write check | `src/ufsd#fil.c:593-595` | observed |
| unlink (REMOVE) | mount write check | `src/ufsd#fil.c:707-709` | observed |
| chdir | none | `src/ufsd#fil.c:619-660` | observed |
| opendir / readdir | none | `src/ufsd#fil.c:1195-1258, 1270-1414` | observed |
| stat | none | `src/ufsd#fil.c:1470-1530` | observed |
| chmod, chown, rename, link, symlink, utime | **operation does not exist** (no function code) | `include/ufsd.h:377-397` | observed |
| traversal (search permission on directories) | none; mode bits are never read for access decisions | `src/ufsd#dir.c:238-325` | observed |

- New files always get mode `0644` and new directories `0755`, with owner and group copied from the session. libufs `create_perm` is local only and never sent. (`src/ufsd#fil.c:526, 531-532, 820-824`; `client/libufs.c:185`.)
- Mount OWNER and MODE come from `UFSDPRM0` or the operator `MODIFY MOUNT`. A mount without OWNER is writable by every session. (`samplib/ufsdprm0:8-16`; `src/ufsd#cmd.c:233-244`.)

## U-5 Sessions, handles and termination (item 5)

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 5.1 | There are 64 sessions. Token = `((slot+1)<<16) \| (serial & 0xFFFF)`, with a single serial counter in the STC. Tokens are predictable. | `src/ufsd#ses.c:6-9, 204-206`; `include/ufsd.h:463` | observed |
| 5.2 | **A token is not bound to its ASID.** `ufsd_sess_find` checks the slot, the ACTIVE flag and token equality only. Any authorized client presenting another session's token gets that session's fds, cwd and identity. | `src/ufsd#ses.c:144-161`; `src/ufsd#que.c:175, 198` | observed |
| 5.3 | There are 64 fds per session, mapped to a global table of 256 open-file entries (position, open mode, refcount). The refcount is always 1, so there is no sharing, dup or fork semantics. | `include/ufsd.h:462, 476-479, 504, 522-530`; `src/ufsd#gft.c:84-118` | observed |
| 5.4 | A clean `SESS_CLOSE` releases all fds and the per-session cwd. | `src/ufsd#ses.c:255-284` | observed |
| 5.5 | **A client that ends or ABENDs without `SESS_CLOSE` leaves its session, fds and GFT entries allocated.** They are reclaimed only when the operator runs `F UFSD,SESSIONS PRUNE`. Nothing calls the cleanup automatically. | `src/ufsd#ses.c:379-445`; `src/ufsd#cmd.c:133-137` (only call site) | observed |
| 5.6 | PRUNE treats a session as live while its ASID is assigned. **Hypothesis:** if the ASID has been reused by another address space, a stale session survives PRUNE. Combined with 5.2, this lets the new owner of that ASID use the old session. | `src/ufsd#ses.c:403-414` | observed (logic); hypothesis (exploitability) |
| 5.7 | A client cancelled while it waits in the router leaves its request block on the queue. The STC later posts an ECB on a stack that no longer exists, through an ASCB that may be gone, and the request block is never returned to the 32-entry pool (only the router frees it). **Hypothesis:** repeated cancels exhaust the pool (`UFSD_RC_NOREQ`) or post into freed storage. | `src/ufsd#que.c:12-16, 288`; `src/ufsd#ssi.c:329-336`; `src/ufsd#ssi.c:270-273` (comment: "The request block stays orphaned") | hypothesis |
| 5.8 | The router's wait has no overall timeout and no cancellation. It re-waits every 5 s while the server stays ACTIVE. | `src/ufsd#ssi.c:49-57, 248-288` | observed |
| 5.9 | If the STC ABENDs, ESTAE nulls the SSVT entry and clears ACTIVE but keeps CSA. Waiting clients return `UFSD_RC_CORRUPT` at their next 5 s check. The next start reclaims the orphaned CSA, and `UFSDCLNP` is the fallback. | `src/ufsd.c:92-140, 349`; `include/ufsd.h:594-653`; `src/ufsd#ssi.c:255-283` | observed (code), documented (design) |

## U-6 Concurrency and locking (item 6)

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 6.1 | The server is single-threaded. One STC task drains the queue and serves requests one at a time, so each request is atomic with respect to the others. | `src/ufsd.c:509-534`; `internals/concept.md:521`; `docs/books/ref/ref-lim.typ:75-78` | observed / documented |
| 6.2 | The client side is lock-free: CS push onto `req_head`, the server takes the whole chain, and the pools use CDS with an ABA tag. | `include/ufsd.h:253-290`; `src/ufsd#ssi.c:67-77, 221` | observed |
| 6.3 | **No ENQ, RESERVE or file locks** appear anywhere in `src/`, `client/` or `include/`. Two clients writing the same file are not kept apart. Each has its own position, and the last write wins per block. | grep (none found) at the pin; `docs/books/ref/ref-lim.typ:76-78` | observed / documented |
| 6.4 | Read-write mounts are allocated `DISP=OLD` and read-only mounts `DISP=SHR`, which is the only data-set serialization. **Hypothesis:** a batch job holding a read-write UFS data set `SHR` blocks the mount, and a read-only mount does not stop another job from writing the data set. | `src/ufsd#ini.c:86-93, 456-457` | observed (code), hypothesis (effect) |
| 6.5 | A multi-worker design (phase 5) is planned but not implemented. | `internals/concept.md:546` | documented |

## U-7 Backing store (item 7)

| # | Claim | Evidence | Confidence |
|---|---|---|---|
| 7.1 | Each file system is one BDAM data set, opened for update. Blocks of 512–8192 bytes (default 4096) are accessed by relative block number with `osdread`/`osdwrite` and `oscheck`. I/O errors go to SYNAD, with one WTO per disk. | `src/ufsd#blk.c:1-80`; `src/ufsd#ini.c:166-210`; `docs/books/ref/ref-lim.typ:61-64` | observed |
| 7.2 | The format is V7-UFS (ufs370-compatible): boot block, 512-byte superblock, 128-byte inodes, 64-byte directory entries with names up to 59 characters, 16 direct blocks plus 1 single-indirect block. Owner and group are 8-character strings, **not numeric UID/GID**. | `include/ufsd.h:72-151`; `internals/ufsdisk-spec.md` §3–6 | observed |
| 7.3 | Limits: 16 mounts, 64 sessions, 64 fds per session, 256 open files in total, 32 request blocks, 16 buffers, 1024 entries per directory at 4K, maximum file size `(16 + b/4) × b` (4.06 MB at 4K), inode count fixed at format. | `docs/books/ref/ref-lim.typ:12-68, 85-103`; `include/ufsd.h:462-468, 504` | documented |
| 7.4 | Mounts are configured by `UFSDPRM0` statements `ROOT DSN(..)` and `MOUNT DSN(..) PATH(..) MODE(RO\|RW) OWNER(..)`, read from `DD:UFSDPRM`, and by the operator `F UFSD,MOUNT/UNMOUNT`. The default mode is RO. | `src/ufsd#cfg.c:3-10, 123, 160-209`; `samplib/ufsdprm0:1-20`; `src/ufsd#cmd.c:169-244` | observed |
| 7.5 | **Unmount does not check for open files and compacts the disk array.** Open GFT entries and session cwds store a disk *index*, so after unmounting disk *k*, a handle on disk *k+1* addresses a different file system by inode number. **Hypothesis:** this causes reads and writes against the wrong file system. | `src/ufsd#ini.c:774-830` (compaction l.821-828); `include/ufsd.h:219, 525`; `src/ufsd#fil.c:945, 1093, 1302` | observed (code); hypothesis (runtime effect) |
| 7.6 | There is no journal and **no fsck** (fsck is planned for ufsd-utils, phase 6). `F UFSD,REBUILD` rescans the inodes and rebuilds the free caches. *Corrected after review (2026-11-26):* the earlier claim that every multi-step update fails safe was wrong; see 7.6a. For **inodes** the order is safe: `inode_release` clears the inode on disk before its number enters the cache, so a failure leaks the inode rather than reusing it. | `src/ufsd#fil.c:350-366`; `src/ufsd#sbl.c:14-25, 534-567`; `src/ufsd#cmd.c:333-356`; `internals/concept.md:547` | observed / documented |
| 7.6a | **Blocks can be handed out twice after an I/O failure.** `blk_free_all` pushes each direct block into the in-memory free cache (`ufsd_sb_free_block`, which only appends to `disk->sb.freeblock[]`) and clears `addr[i]` only in the in-memory inode copy. Only then does it read the indirect block, and the caller writes the inode back later still. If any of these fails, the inode on disk still references blocks that are already free to allocate: (a) the indirect-block read fails after the direct blocks were freed (l.317-332);  (b) truncate-on-open fails at `ufsd_ino_write` after a successful `blk_free_all` (l.794-800);  (c) unlink fails in `inode_release` after `blk_free_all` (l.723-727; the directory entry is already gone, l.714). The next `ufsd_sb_alloc_block` can give those blocks to another file, cross-linking two inodes. A later successful request that calls `ufsd_sb_write` persists the cache to disk. REBUILD repairs this only if it runs before any reuse. The upstream comment "the disk is left in a state MODIFY REBUILD reconciles" (l.304-306) does not hold once an allocation intervenes. | `src/ufsd#fil.c:304-306, 308-347, 714-727, 794-801`; `src/ufsd#sbl.c:227-243` | observed (code path); runtime is a **hypothesis** that needs an OSE-006 fault-injection test on a disposable image |
| 7.7 | A known upstream defect: the free-block and free-inode caches overflow on mass delete and leak until REBUILD. | `internals/concept.md:513-516` | documented |
| 7.8 | `ufs_sync` is a no-op. `ufs_fsync` only flushes the client write-behind buffer. There is no server-side cache, so every request reads and writes BDAM directly. | `client/libufs.c:818-829`; `src/ufsd#fil.c:16` | observed |
| 7.9 | No backup procedure is documented in `docs/` or the user guide at the pin. A file system is a plain data set. **Hypothesis:** a data-set copy is consistent only while it is unmounted or UFSD is stopped. | grep of `docs/` at the pin | observed (absence); hypothesis (method) |
| 7.10 | **Hypothesis (from recon R-06):** under the default RAKF `DATASET * READ`, any user can read the backing data sets directly, bypassing UFSD entirely. Owner: OSE-007. | recon R-06 | hypothesis |

## U-8 Public libufs API (item 8)

There are 38 declarations in `include/libufs.h:176-244`. The table is in [ufsd-observed.md §4](../interfaces/ufsd-observed.md#4-libufs-public-api). Semantics that matter for OSE-012 and the compatibility table:

- `ufs_fopen` mode: `r` or `R` means read. **Every other mode string means write, which creates or truncates**, so `"a"` truncates (`client/libufs.c:739-743`; `src/ufsd#fil.c:784-801`).
- `ufs_fseek` always returns -1, and the server has no SEEK function, only a reserved code 0x24 (`client/libufs.c:1137-1144`; `include/ufsd.h:387`).
- `ufs_diropen` ignores its `pattern` argument (`client/libufs.c:557`).
- There is no rename, link, chmod, chown, utime, truncate, access or dup.
- Path resolution does not interpret `.` and `..`. They are looked up as ordinary directory entries, so `..` at the root of a mounted disk stays on that disk (`src/ufsd#dir.c:236`).
- Return codes are `UFSD_RC_*`. `-1` means the SSI request did not arrive (`client/libufs.c:37-40`).

## U-9 Gap list against spec §3.3 and §3.4 (item 9)

Ratings: **M1** = blocks the M1 shell and filesystem milestone. **M3** = blocks the M3 security and multi-user milestone. **later** = needed eventually, no milestone gate yet. Proposed owners are suggestions for the coordinator.

| ID | Gap | Spec | Evidence | Rating | Proposed owner |
|---|---|---|---|---|---|
| G-1 | Identity is client-asserted (`SESS_OPEN`/`SETUSER`). | §3.4 "no client-trusted identity" | U-3 | **M1** (the OSE ABI must not inherit it) and **M3** (enforcement) | OSE-007 → OSE-010 |
| G-2 | All clients must be APF-authorized, and libufs runs in the caller's address space, so untrusted OSE code cannot be a UFSD client. A trusted broker is needed. | §3.2, §3.4 | U-1.4 | **M1** (architecture) | OSE-007, OSE-010 |
| G-3 | No mode-bit, ownership or traversal enforcement; no numeric UID/GID on disk. | §3.4 | U-4, U-7.2 | **M3** | OSE-010 / later card |
| G-4 | Sessions are not bound to an ASID, tokens are predictable, and cleanup after ABEND is manual. | §3.4 threat model "cross-user handle access, identity reuse" | U-5.1, 5.2, 5.5, 5.6 | **M3**; also **M1** for resource leaks in a long-running shell | OSE-006 (tests), OSE-010 |
| G-5 | Raw key-0 dereference of client pointers (`buf_ptr`) and no version, length or correlation fields in requests. | §3.2 | U-2.1, 2.3 | **M1** for the OSE ABI (do not copy it); **M3** if UFSD remains reachable | OSE-010 |
| G-6 | Unmount with open handles redirects them to another file system. | §3.3 "mount handling", "corruption recovery" | U-7.5 | **M1** (data integrity) | OSE-006 (prove), upstream issue (needs human approval) |
| G-7 | No seek, append, rename, links or chmod/chown; `"a"` truncates; `errno` is always 0. | §3.3 "open flags, EOF, seek, append" | U-2.5, U-8 | **M1** for seek/append/errno mapping; rename and links **later** | OSE-010 / M1 filesystem card |
| G-8 | No file locking; single-threaded server. | §3.3 "locking semantics" | U-6 | **later** (document for M1) | OSE-010 |
| G-9 | No fsck, no journal, no documented backup; free-cache leak defect. | §3.3 "corruption recovery, backup" | U-7.6, 7.7, 7.9 | **later**; document the limits for M1 | runbook card |
| G-15 | An I/O failure during truncate or unlink can leave blocks both referenced by an inode and present in the free cache, so they can be allocated twice (cross-linked files). | §3.3 "corruption recovery"; §3.4 "metadata updates atomic or recoverable" | U-7.6a | **M1** (data integrity) | OSE-006 (fault-injection test on a disposable image), upstream issue (needs human approval) |
| G-10 | File limit about 4 MB at 4K, directories up to 1024 entries, names up to 59 characters, 16 mounts. | §3.3 "size limits" | U-7.3 | **later** (document for M1; affects `/usr` tooling) | OSE-010 |
| G-11 | Request data in CSA is readable by any address space while in flight. | §3.4 "common storage" | U-2.7 | **M3** | OSE-007 |
| G-12 | Alternate paths: direct data-set access (R-06), and FTPD, HTTPD and mvsMF as libufs clients that set identity themselves. | §3.3 "must not bypass enforcement" | U-3.7, U-7.10 | **M3** | OSE-007 |
| G-13 | Encoding: names and data are stored as raw bytes, with an informational `codepage` field. Text conversion is the client's job. | §3.3 encoding | `include/ufsd.h:137`; `internals/ufsdisk-spec.md` §12 | **M1** (define the policy; UFSD itself does not block it) | OSE-010 |
| G-14 | Request-pool and session exhaustion (32 requests, 64 sessions) is reachable by any authorized client. | §3.4 "storage exhaustion" | U-5, U-7.3 | **M3** | OSE-006 |

## Escalations

- **To OSE-007 (high tier):** G-1, G-2, G-11 and G-12, U-3 in full, and the question in U-1.7 of who may obtain APF authorization through RAKF SVC 244. These are the card's escalation trigger "cannot determine identity": in fact identity *is* determined, and it is unverified by design.
- **Undocumented authorized paths:** none found beyond the documented SSI router and the reclaim, cleanup and format utilities (`src/ufsd#rcl.c`, `src/ufsdclnp.c`). The key-0 `buf_ptr` copies (U-2.3) are in documented code but carry no validation. Flagged for OSE-007.
- **Upstream reports** (U-3.5 doc mismatch, U-7.5 unmount, U-5.7 orphaned requests, U-7.6a block double allocation) need human approval before any outreach (AGENTS.md).

## Not done in this task

- No guest test. Every **hypothesis** row needs a negative or positive test in OSE-006 under a lease.
- FTPD, HTTPD and mvsMF were not read (U-3.7 is a lead).
- `src/ufsfmt.c` (formatter) and `src/ufsd#rcl.c` (reclaim) were read only as far as the cited lines.

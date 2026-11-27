# Runbook: build the CC/370 toolchain and the hello load module (OSE-004)

Last verified: 2026-11-27, on branch `task/OSE-004-guest`, Windows 11 + Docker Desktop 29.9.3 (Git Bash). **Host part** (2026-11-26) and **guest part** (2026-11-27) verified: toolchain, libc, hello load module, deploy, batch and TSO run.

## Prerequisites
- Docker with a running engine. Git and a POSIX `sh` (Git Bash on Windows). GNU make is optional: `make build` only calls `sh scripts/build.sh all`.
- Network access to github.com and the Debian mirror the first time.
- About 2 GB free under `artifacts/` (git-ignored).

## Commands

| Step | Command | Success looks like | Failure looks like |
|---|---|---|---|
| Everything | `make build` (or `sh scripts/build.sh all`) | RC 0, then the version lines, the maclib370 verify line and the sha256 lines below | RC 1 with `build.sh: … failed`; read the log it names under `artifacts/evidence/ose-004/` |
| 1. Toolchain | `sh scripts/build.sh toolchain` | `cc370 1.6.3 (802dde1), based on GCC 3.4.6`, as370 and ld370 at `802dde1`, `verify: 1035 of 1035 members re-encode …` | `cc370-build.log` |
| 2. libc | `sh scripts/build.sh libc` | `libc.a` sha256 `d3a422e8…` | `libc370-build.log` |
| 3. hello | `sh scripts/build.sh hello` | sha256 lines for `hello.s`, `hello.o`, `HELLO`, `HELLO.xmit` | messages above the error; `hello/link.log` |
| Probes (optional) | `PROBE_DIR=<dir with p*.c> sh scripts/build.sh probes` (the OSE-012 probes are on `task/OSE-012-libc-inventory`, in `tests/host/c-probes`) | `pNN rc=…` lines in `probes/summary.txt` | RC 1: no sources or no toolchain |

Expected hashes at the pins:

| File | sha256 |
|---|---|
| `libc.a` | `d3a422e823cfac161cc0cc9107577ef7c3fe5aee103e4a7855395a0b6cd754ab` |
| `hello.o` | `1a1001c4fdc7d8078f9ffe08433ed0583959bce14ed726c94990fd7744954007` |
| `HELLO` | `8175740845632edcdf0af04785c82c67e1d0a24fb3e8bf3871be600c223d636a` |
| `HELLO.xmit` | `0e69e9fa44689fc49a27541084f9cd77ff715f761772a3c98e664529857d0d9f` |

The build pins the assembly and link timestamps (`ASMDATE`, `ASMTIME`, `LDDATE`, `LDTIME` in `scripts/build.sh`), so these hashes repeat. If one differs, record the new value and find the cause before going on. The Debian packages are not snapshot-pinned, but they only build the host tools.

**Worktree smoke check** (review R04-1; run it after any change to `scripts/build.sh`). Run the build from a fresh Git worktree, whose `.git` is a file pointing at host-side metadata that the container cannot see:

```sh
git worktree add --detach artifacts/wt-smoke HEAD
(cd artifacts/wt-smoke && sh scripts/build.sh all)    # expect RC 0 and the hashes above
git worktree remove --force artifacts/wt-smoke
```

Last run: 2026-11-26, RC 0, with all five hashes as above. It takes about 4 minutes, because the worktree clones its own pinned sources.

`scripts/build.sh` pins the image by digest and every source by full commit SHA. It refuses a clone that is not at its pin or that has local changes.

## Deploy and run on the guest (acceptance 2-4)
Prerequisites: `make build` (HELLO.xmit at the hash above; `deploy.sh` refuses any other), the OSE-003 image and a sysgen'd volume, and the **guest lease**. Use a disposable copy of the reference volume, so `ose-sysgen-1` stays as built:

```sh
docker volume create ose-guest-004
docker run --rm --user 0 -v ose-sysgen-1:/from:ro -v ose-guest-004:/to ose-hercules:4.9.1-ee86c4de sh -c 'cp -a /from/. /to/'
export DASD_VOLUME=ose-guest-004
```

| Step | Command | Success looks like | Failure looks like |
|---|---|---|---|
| Deploy (acceptance 2) | `make deploy` (= `sh scripts/deploy.sh deploy`) | RC 0; `OSEHDEP: step DELOLD … 0000`, `GONE … 0004`, `STAGE`, `RECV`, `CLEANUP … 0000`; then `OSEHLST: MVSCE02.OSE.LOAD members ['HELLO']` | RC 1 with `MISMATCH` or an empty member list; read `<mode>-prt00e.txt` |
| Batch and TSO (acceptance 3, 4) | `sh scripts/deploy.sh run` | RC 0; `step RC0 … 0000`, `step RC4 … 0004`, output lines `['OSE-004 HELLO RC=0', 'OSE-004 HELLO RC=4']`, `TSO: {... 'call_plain': True ... 'logoff': True}` | RC 1; the TSO screens are `tso-NN-*.txt` |
| Both | `sh scripts/deploy.sh all` | both of the above, about 3.5 minutes | |

How it works:
1. The deck goes to the EBCDIC card reader (`001A`, port 3506): the job `jcl/hello/deploy.jcl` with the XMIT's raw records in-stream behind `DD DATA,DLM=`. No FTPD and no mvsMF are involved. RECEIVE unpacks the XMIT into `<user>.OSE.LOAD` on PUB000.
2. Step GONE must find the old library deleted (LISTCAT CC 4) before anything is received. A stale library can therefore never pass as a fresh deploy.
3. A separate job, `jcl/hello/list.jcl`, lists the members. Acceptance 2 relies on that listing, not on the deploy's RCs.
4. `jcl/hello/run.jcl` runs HELLO twice. The step RC must equal the PARM (0, 4), and SYSPRINT must hold exactly the expected line, parsed from the JES2 printer file.
5. TSO: the driver logs on as MVSCE02, enters `CALL '<user>.OSE.LOAD(HELLO)' '7'` and expects `OSE-004 HELLO RC=7`. If that line does not appear, it tries again after `ALLOC F(SYSPRINT) DA(*)` and records which of the two worked.

Each mode is one cold IPL with the OSE-003 shutdown rules: `$HASP099`, `$HASP085` and `IEE334I` in order after the shutdown request. The user is MVSCE02; its password is read at run time from the volume's `users.conf` and redacted from every saved file.

Evidence: a new directory per invocation, `artifacts/evidence/ose-004/guest/runs/<UTC>-<pid>/<mode>/`, holding `console.txt`, `<mode>-result.json`, `<mode>-prt00e.txt`, `<mode>-mvslog.txt` and the TSO screens. Earlier runs are never overwritten.

Observed 2026-11-27 on `ose-guest-004`: deploy RC 0 five times (about 54 s each; three of them re-deploys over an existing library) and run RC 0 four times (about 120 s each).


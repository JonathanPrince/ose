"""OSE-009 guest harness: leases, snapshots and restore for MVS/CE guest volumes.

Package-neutral: a guest is a Docker volume holding sysgen/MVSCE/ (DASD, conf,
printers) and sysgen/users.conf, as produced by OSE-003. Nothing here depends
on OSE, HELLO or any package.

  guest.py lease acquire --volume V --task T [--owner O] [--holder-pid P]   -> prints the token
  guest.py lease check   --volume V --token X
  guest.py lease release --volume V --token X
  guest.py lease status  [--volume V]
  guest.py lease break   --volume V          (only a stale lease: holder process gone)
  guest.py snapshot create --volume V --name N --token X
  guest.py snapshot verify --name N
  guest.py snapshot list
  guest.py restore --volume V --name N --token X [--create]

Leases live in a host-wide directory (OSE_LEASE_DIR, default ~/.ose-guest/leases),
because Docker volumes are host-wide and several worktrees share them. A lease is
created atomically (O_CREAT|O_EXCL); a second acquire fails and names the holder.
A lease whose holder process is gone is reported as stale and is never taken
over silently: `lease break` removes it explicitly, and only when stale.
Snapshots live in artifacts/guest/snapshots/<name>/ with sha256 manifests; restore
verifies them before touching the volume and refuses a corrupted snapshot.
Every command logs to artifacts/guest/logs/ and exits nonzero on failure:
  1 error, 2 usage, 3 lease held by someone else, 4 lease stale, 5 volume busy,
  6 snapshot invalid, 7 restore failed (volume left as it was).
"""
import argparse
import datetime
import getpass
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "guest"
SNAPDIR = Path(os.environ.get("OSE_SNAPSHOT_DIR", ART / "snapshots"))
LOGDIR = Path(os.environ.get("OSE_GUEST_LOG_DIR", ART / "logs"))
LEASEDIR = Path(os.environ.get("OSE_LEASE_DIR", Path.home() / ".ose-guest" / "leases"))
# OSE_DOCKER: a program name, or a JSON list for a command prefix (tests run a fake
# docker script through bash this way; Windows paths do not survive shell splitting)
_DOCKER_ENV = os.environ.get("OSE_DOCKER", "docker")
DOCKER = json.loads(_DOCKER_ENV) if _DOCKER_ENV.startswith("[") else [_DOCKER_ENV]
NAME_RX = re.compile(r"[a-z0-9][a-z0-9_.-]{0,62}")
E_ERROR, E_USAGE, E_HELD, E_STALE, E_BUSY, E_SNAP, E_RESTORE = 1, 2, 3, 4, 5, 6, 7


class Fail(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_LOG = None


def log(msg):
    global _LOG
    if _LOG is None:
        LOGDIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        _LOG = (LOGDIR / f"{stamp}-{os.getpid()}.log").open("a", encoding="utf-8")
    _LOG.write(f"[{now()}] {msg}\n")
    _LOG.flush()


def say(msg):
    print(msg)
    log(msg)


def herc_image():
    """The pinned Hercules image tag, read from scripts/lib/common.sh (one source of truth)."""
    if os.environ.get("OSE_HERC_IMAGE"):
        return os.environ["OSE_HERC_IMAGE"]
    text = (ROOT / "scripts" / "lib" / "common.sh").read_text(encoding="utf-8")
    ver = re.search(r"^HERCULES_VERSION=(\S+)", text, re.M).group(1)
    com = re.search(r"^HERCULES_COMMIT=([0-9a-f]{40})", text, re.M).group(1)
    return f"ose-hercules:{ver}-{com[:8]}"


def docker(*args, check=True, capture=True):
    log("docker " + " ".join(args))
    try:
        p = subprocess.run([*DOCKER, *args], capture_output=capture, text=True)
    except OSError as e:
        raise Fail(E_ERROR, f"cannot run docker ({DOCKER}): {e}")
    if capture:
        if p.stdout.strip():
            log("  stdout: " + p.stdout.strip()[-2000:])
        if p.stderr.strip():
            log("  stderr: " + p.stderr.strip()[-2000:])
    log(f"  rc={p.returncode}")
    if check and p.returncode != 0:
        raise Fail(E_ERROR, f"docker {args[0]} failed (rc {p.returncode}): {(p.stderr or '').strip()[-300:]}")
    return p


def check_name(kind, value):
    if not NAME_RX.fullmatch(value or ""):
        raise Fail(E_USAGE, f"invalid {kind} name {value!r} (lower case, digits, _ . -)")


# ------------------------------------------------------------------ processes
def pid_alive(pid: int) -> bool:
    """True if a process with this PID exists on this host. On Windows os.kill(pid, 0)
    would terminate the process, so the Win32 API is queried instead."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return True
            return code.value == 259                     # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ------------------------------------------------------------------ leases
def lease_path(volume):
    return LEASEDIR / f"{volume}.lease"


def read_lease(volume):
    p = lease_path(volume)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as e:
        raise Fail(E_ERROR, f"lease file {p} unreadable: {e}")


def lease_state(lease):
    """'alive', 'stale' (holder gone on this host) or 'foreign' (other host: cannot check)."""
    if lease.get("host") != socket.gethostname():
        return "foreign"
    return "alive" if pid_alive(int(lease.get("holder_pid", 0))) else "stale"


def describe(lease):
    return (f"task {lease.get('task')} owner {lease.get('owner')} pid {lease.get('holder_pid')} "
            f"host {lease.get('host')} since {lease.get('acquired')}")


def running_containers(volume):
    p = docker("ps", "-q", "--filter", f"volume={volume}", check=False)
    return [c for c in p.stdout.split() if c]


def cmd_lease_acquire(a):
    check_name("volume", a.volume)
    LEASEDIR.mkdir(parents=True, exist_ok=True)
    held = read_lease(a.volume)
    if held:
        st = lease_state(held)
        if st == "stale":
            raise Fail(E_STALE, f"lease on {a.volume} is STALE (holder process gone): {describe(held)}; "
                                f"inspect, then `guest.py lease break --volume {a.volume}`")
        raise Fail(E_HELD, f"lease on {a.volume} is held: {describe(held)}")
    busy = running_containers(a.volume)
    if busy and not a.allow_running:
        raise Fail(E_BUSY, f"volume {a.volume} is in use by running container(s) {busy} without a lease")
    lease = {"volume": a.volume, "task": a.task, "owner": a.owner or getpass.getuser(),
             "holder_pid": int(a.holder_pid or os.getppid()), "host": socket.gethostname(),
             "acquired": now(), "token": secrets.token_hex(16)}
    try:
        fd = os.open(lease_path(a.volume), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        other = read_lease(a.volume) or {}
        raise Fail(E_HELD, f"lease on {a.volume} was taken concurrently: {describe(other)}")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(lease, f)
    log(f"lease acquired {a.volume}: {describe(lease)}")
    print(lease["token"])


def require_lease(volume, token):
    lease = read_lease(volume)
    if not lease:
        raise Fail(E_HELD, f"no lease on {volume}: acquire one first")
    if not token or not secrets.compare_digest(lease.get("token", ""), token):
        raise Fail(E_HELD, f"lease on {volume} belongs to someone else: {describe(lease)}")
    if lease_state(lease) == "stale":
        raise Fail(E_STALE, f"lease on {volume} is stale (holder process gone): {describe(lease)}")
    return lease


def cmd_lease_check(a):
    lease = require_lease(a.volume, a.token)
    say(f"lease ok {a.volume}: {describe(lease)}")


def cmd_lease_release(a):
    lease = read_lease(a.volume)
    if not lease:
        raise Fail(E_HELD, f"no lease on {a.volume}")
    if not secrets.compare_digest(lease.get("token", ""), a.token or ""):
        raise Fail(E_HELD, f"not your lease on {a.volume}: {describe(lease)}")
    lease_path(a.volume).unlink()
    say(f"lease released {a.volume}")


def cmd_lease_status(a):
    files = [lease_path(a.volume)] if a.volume else sorted(LEASEDIR.glob("*.lease")) if LEASEDIR.exists() else []
    found = False
    for p in files:
        lease = read_lease(p.stem)
        if lease:
            found = True
            print(f"{p.stem}: {lease_state(lease).upper()} {describe(lease)}")
    if not found:
        print("no leases" + (f" on {a.volume}" if a.volume else ""))


def cmd_lease_break(a):
    lease = read_lease(a.volume)
    if not lease:
        raise Fail(E_HELD, f"no lease on {a.volume}")
    st = lease_state(lease)
    if st != "stale":
        raise Fail(E_HELD, f"refusing to break a {st} lease on {a.volume}: {describe(lease)}")
    lease_path(a.volume).unlink()
    say(f"stale lease broken on {a.volume}: {describe(lease)}")


# ------------------------------------------------------------------ snapshots
def sha256_file(p: Path):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def mount(p: Path):
    return p.resolve().as_posix()                       # C:/... on Windows, /... elsewhere


def require_stopped(volume):
    busy = running_containers(volume)
    if busy:
        raise Fail(E_BUSY, f"volume {volume} has running container(s) {busy}; stop the guest first")


def cmd_snapshot_create(a):
    check_name("volume", a.volume)
    check_name("snapshot", a.name)
    require_lease(a.volume, a.token)
    require_stopped(a.volume)
    d = SNAPDIR / a.name
    if d.exists():
        raise Fail(E_USAGE, f"snapshot {a.name} exists: {d}")
    tmp = SNAPDIR / f".{a.name}.partial-{os.getpid()}"
    tmp.mkdir(parents=True)
    try:
        img = herc_image()
        docker("run", "--rm", "--user", "1000:1000", "-v", f"{a.volume}:/work:ro", "-v", f"{mount(tmp)}:/out", img,
               "sh", "-c", "set -e; test -d /work/sysgen/MVSCE; test -f /work/sysgen/users.conf; cd /work; "
               "find sysgen/MVSCE sysgen/users.conf -type f | LC_ALL=C sort | xargs sha256sum > /out/files.sha256; "
               "tar -cf /out/guest.tar sysgen/MVSCE sysgen/users.conf")
        files = (tmp / "files.sha256").read_text(encoding="utf-8").splitlines()
        meta = {"name": a.name, "source_volume": a.volume, "created": now(), "image": img,
                "files": len(files), "tar_bytes": (tmp / "guest.tar").stat().st_size, "note": a.note or ""}
        (tmp / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        sums = "".join(f"{sha256_file(tmp / n)}  {n}\n" for n in ("guest.tar", "files.sha256", "meta.json"))
        (tmp / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
        tmp.rename(d)
    except BaseException:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    say(f"snapshot {a.name} created from {a.volume}: {meta['files']} files, {meta['tar_bytes']} bytes, {d}")


def verify_snapshot(name):
    """Return the snapshot directory if every manifest entry matches; raise E_SNAP otherwise."""
    check_name("snapshot", name)
    d = SNAPDIR / name
    sums = d / "SHA256SUMS"
    if not sums.is_file():
        raise Fail(E_SNAP, f"snapshot {name}: no SHA256SUMS in {d}")
    want = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"([0-9a-f]{64})  (\S+)", line)
        if not m:
            raise Fail(E_SNAP, f"snapshot {name}: malformed SHA256SUMS line {line!r}")
        want[m.group(2)] = m.group(1)
    if set(want) != {"guest.tar", "files.sha256", "meta.json"}:
        raise Fail(E_SNAP, f"snapshot {name}: SHA256SUMS lists {sorted(want)}")
    for n, h in want.items():
        p = d / n
        if not p.is_file():
            raise Fail(E_SNAP, f"snapshot {name}: {n} missing")
        got = sha256_file(p)
        if got != h:
            raise Fail(E_SNAP, f"snapshot {name}: {n} sha256 {got} does not match the manifest {h} (corrupted)")
    log(f"snapshot {name} verified")
    return d


def cmd_snapshot_verify(a):
    verify_snapshot(a.name)
    say(f"snapshot {a.name} OK")


def cmd_snapshot_list(a):
    if not SNAPDIR.exists():
        print("no snapshots")
        return
    for d in sorted(p for p in SNAPDIR.iterdir() if p.is_dir() and not p.name.startswith(".")):
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            print(f"{d.name}: from {meta.get('source_volume')} at {meta.get('created')}, {meta.get('files')} files")
        except (OSError, json.JSONDecodeError):
            print(f"{d.name}: unreadable meta.json")


# Runs in a helper container: extract into a scratch directory on the same volume,
# check every file against files.sha256, and only then swap directories. Any failure
# before the swap leaves the guest untouched; a failed swap puts the old MVSCE back.
RESTORE_SH = r"""set -u
R=/work/.restore-$1
fail() { echo "restore: $*" >&2; rm -rf "$R"; exit 7; }
rm -rf "$R" && mkdir -p "$R" || fail "cannot create $R"
tar -C "$R" -xf /snap/guest.tar || fail "tar extraction failed"
( cd "$R" && sha256sum -c --quiet /snap/files.sha256 ) || fail "extracted files do not match files.sha256"
mkdir -p /work/sysgen || fail "cannot create /work/sysgen"
if [ -e /work/sysgen/MVSCE ]; then mv /work/sysgen/MVSCE "$R/MVSCE.previous" || fail "cannot move the old MVSCE aside"; fi
if ! mv "$R/sysgen/MVSCE" /work/sysgen/MVSCE; then
    [ -e "$R/MVSCE.previous" ] && mv "$R/MVSCE.previous" /work/sysgen/MVSCE
    echo "restore: swap failed; previous MVSCE put back" >&2; exit 7
fi
cp "$R/sysgen/users.conf" /work/sysgen/users.conf.new && mv /work/sysgen/users.conf.new /work/sysgen/users.conf \
    || { echo "restore: users.conf not replaced" >&2; exit 7; }
rm -rf "$R"
echo restored
"""


def cmd_restore(a):
    check_name("volume", a.volume)
    d = verify_snapshot(a.name)                         # refuse a corrupted snapshot before anything else
    img = herc_image()
    exists = docker("volume", "inspect", a.volume, check=False).returncode == 0
    if not exists:
        if not a.create:
            raise Fail(E_USAGE, f"volume {a.volume} does not exist (use --create for a new guest)")
        docker("volume", "create", a.volume)
        docker("run", "--rm", "--user", "0", "-v", f"{a.volume}:/work", img, "chown", "1000:1000", "/work")
        say(f"created volume {a.volume}")
    require_lease(a.volume, a.token)
    require_stopped(a.volume)
    p = docker("run", "--rm", "--user", "1000:1000", "-v", f"{a.volume}:/work", "-v", f"{mount(d)}:/snap:ro", img,
               "sh", "-c", RESTORE_SH, "restore", str(os.getpid()), check=False)
    if p.returncode != 0 or "restored" not in p.stdout:
        raise Fail(E_RESTORE, f"restore of {a.name} into {a.volume} failed (rc {p.returncode}): "
                              f"{p.stderr.strip()[-300:]}; the volume's previous MVSCE was kept")
    say(f"restored snapshot {a.name} into {a.volume}")


# ------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(prog="guest.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lease = sub.add_parser("lease").add_subparsers(dest="op", required=True)
    p = lease.add_parser("acquire")
    p.add_argument("--volume", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--owner")
    p.add_argument("--holder-pid", type=int, help="process whose life the lease follows (default: caller)")
    p.add_argument("--allow-running", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_lease_acquire)
    for op, fn in (("check", cmd_lease_check), ("release", cmd_lease_release)):
        p = lease.add_parser(op)
        p.add_argument("--volume", required=True)
        p.add_argument("--token", required=True)
        p.set_defaults(fn=fn)
    p = lease.add_parser("status")
    p.add_argument("--volume")
    p.set_defaults(fn=cmd_lease_status)
    p = lease.add_parser("break")
    p.add_argument("--volume", required=True)
    p.set_defaults(fn=cmd_lease_break)
    snap = sub.add_parser("snapshot").add_subparsers(dest="op", required=True)
    p = snap.add_parser("create")
    p.add_argument("--volume", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--note")
    p.set_defaults(fn=cmd_snapshot_create)
    p = snap.add_parser("verify")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=cmd_snapshot_verify)
    p = snap.add_parser("list")
    p.set_defaults(fn=cmd_snapshot_list)
    p = sub.add_parser("restore")
    p.add_argument("--volume", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--create", action="store_true")
    p.set_defaults(fn=cmd_restore)
    a = ap.parse_args(argv)
    try:
        log(f"guest.py {' '.join(argv if argv is not None else sys.argv[1:])}".replace(getattr(a, "token", "") or "\0", "<token>"))
        a.fn(a)
        return 0
    except Fail as e:
        print(f"guest.py: {e}", file=sys.stderr)
        log(f"FAIL ({e.code}): {e}")
        return e.code


if __name__ == "__main__":
    sys.exit(main())

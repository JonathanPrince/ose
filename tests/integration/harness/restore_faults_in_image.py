"""OSE-009 R09-2 check in the pinned Hercules image: run the real RESTORE_SH (as
`guest.py restore` runs it, sh in Debian) against tiny bind-mounted fixtures, with
the same four fault cases as the host tests. No guest volume is involved.

  python -I tests/integration/harness/restore_faults_in_image.py [--out DIR]
Exit 0 only if every case gives the expected exit code and guest content.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("guest", ROOT / "scripts" / "guest" / "guest.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

OLD = {"MVSCE/DASD/old.3350": b"OLD DASD", "users.conf": b"OLDUSER OLDPW\n"}
NEW = {"MVSCE/DASD/new.3350": b"NEW DASD", "users.conf": b"NEWUSER NEWPW\n"}
MV_WRAP = ('#!/bin/sh\nsrc=\nfor a in "$@"; do case "$a" in -*) ;; *) src=$a; break ;; esac; done\n'
           'case "$src" in {pats} esac\nexec /bin/mv "$@"\n')
CASES = [  # name, fail_mv_from, pre-existing users.conf.new dir, expected rc, expected content
    ("success", [], False, 0, NEW),
    ("staging-blocked", [], True, 7, OLD),
    ("late-users-conf-failure", ["/sysgen/users.conf.new"], False, 7, OLD),
    ("rollback-failure", ["/sysgen/users.conf.new", "/MVSCE.previous"], False, 8, None),
]


def tree(d: Path):
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def build(base: Path, staging_blocked: bool, fail_from):
    snap, work, wrap = base / "snap", base / "work", base / "wrap"
    for d in (snap, work / "sysgen", wrap):
        d.mkdir(parents=True)
    src = base / "src"
    for rel, data in NEW.items():
        (src / "sysgen" / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / "sysgen" / rel).write_bytes(data)
    with tarfile.open(snap / "guest.tar", "w") as t:
        t.add(src / "sysgen", arcname="sysgen")
    lines = [f"{hashlib.sha256((src / 'sysgen' / r).read_bytes()).hexdigest()}  sysgen/{r}" for r in sorted(NEW)]
    (snap / "files.sha256").write_bytes(("\n".join(lines) + "\n").encode())
    for rel, data in OLD.items():
        (work / "sysgen" / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / "sysgen" / rel).write_bytes(data)
    if staging_blocked:
        (work / "sysgen" / "users.conf.new").mkdir()
    (base / "restore.sh").write_bytes(g.RESTORE_SH.encode())
    pats = " ".join(f'*"{s}") exit 1 ;;' for s in fail_from)
    (wrap / "mv").write_bytes(MV_WRAP.format(pats=pats).encode())
    return snap, work, wrap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    img = g.herc_image()
    results, ok = [], True
    for name, fail_from, blocked, want_rc, want in CASES:
        base = Path(tempfile.mkdtemp(prefix=f"r09-{name}-"))
        try:
            snap, work, wrap = build(base, blocked, fail_from)
            cmd = ["docker", "run", "--rm", "--user", "0",
                   "-v", f"{base.resolve().as_posix()}:/fx", img, "sh", "-c",
                   "chmod 755 /fx/wrap/mv && PATH=/fx/wrap:$PATH RESTORE_WORK=/fx/work RESTORE_SNAP=/fx/snap "
                   "sh /fx/restore.sh 4242"]
            p = subprocess.run(cmd, capture_output=True, text=True)
            got = tree(work / "sysgen")
            got.pop("users.conf.new/", None)
            content_ok = True if want is None else (got == want)
            extra = ""
            if name == "rollback-failure":
                kept = list(work.glob(".restore-*"))
                content_ok = bool(kept) and (kept[0] / "MVSCE.previous" / "DASD" / "old.3350").read_bytes() == b"OLD DASD" \
                    and (kept[0] / "users.conf.previous").read_bytes() == OLD["users.conf"]
                extra = "old guest kept in scratch" if content_ok else "old guest NOT kept"
            case_ok = p.returncode == want_rc and content_ok
            ok &= case_ok
            results.append({"case": name, "rc": p.returncode, "expected_rc": want_rc, "content_ok": content_ok,
                            "ok": case_ok, "stderr": p.stderr.strip()[-300:], "note": extra})
            print(f"{name:26} rc={p.returncode} (want {want_rc}) content_ok={content_ok} {'ok' if case_ok else 'FAIL'} {extra}")
        finally:
            shutil.rmtree(base, ignore_errors=True)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "restore-faults-in-image.json").write_text(json.dumps({"image": img, "cases": results}, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

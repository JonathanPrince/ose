#!/usr/bin/env python3
"""Pin enforcement checks for the Sysgen build (OSE-013). Standard library only.

Usage:
  pins.py check-clone COMPONENT DIR     HEAD of the git clone DIR must equal the
                                        lock's commit for COMPONENT (e.g. mvp, rakf)
  pins.py check-mvp-packages DIR        every mvp-pkg-* file DIR/packages/<NAME>
                                        must hash to the lock's sha256 (catches
                                        core.autocrlf-converted checkouts)
Options:
  --lock PATH                           lock file (default: repo dependencies.lock.json)

Exit status: 0 all checks pass; 1 a pin or hash mismatch (each one is named on
stderr); 2 usage error, missing lock, component or path.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_LOCK = Path(__file__).resolve().parents[2] / "dependencies.lock.json"


class UsageError(Exception):
    pass


def load_lock(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise UsageError(f"cannot read lock {path}: {e}") from e


def component(lock: dict, name: str) -> dict:
    for c in lock.get("components", []):
        if c.get("name") == name:
            return c
    raise UsageError(f"component '{name}' not in lock")


def check_clone(lock: dict, name: str, clone: Path) -> list[str]:
    want = component(lock, name)["commit"]
    if not (Path(clone) / ".git").exists():
        raise UsageError(f"{clone} is not a git clone")
    r = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    head = r.stdout.strip() if r.returncode == 0 else "?"
    if head != want:
        return [f"{name}: {clone} is at {head}, lock pins {want}"]
    return []


def mvp_packages(lock: dict) -> dict[str, str]:
    """Map package file name -> sha256 for every mvp-pkg-* entry."""
    out = {}
    for c in lock.get("components", []):
        if c.get("name", "").startswith("mvp-pkg-"):
            fname = c["source_url"].rstrip("/").rsplit("/", 1)[-1]
            out[fname] = c["artifacts"][0]["sha256"]
    return out


def check_mvp_packages(lock: dict, clone: Path) -> list[str]:
    pkgs = mvp_packages(lock)
    if not pkgs:
        raise UsageError("no mvp-pkg-* entries in lock")
    errs = []
    for fname, want in sorted(pkgs.items()):
        f = Path(clone) / "packages" / fname
        if not f.is_file():
            errs.append(f"mvp-pkg {fname}: missing in {clone}/packages")
            continue
        got = hashlib.sha256(f.read_bytes()).hexdigest()
        if got != want:
            errs.append(f"mvp-pkg {fname}: sha256 {got} != lock {want}"
                        " (CRLF-converted checkout? clone with core.autocrlf=false)")
    return errs


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    lock_path = DEFAULT_LOCK
    if "--lock" in args:
        i = args.index("--lock")
        try:
            lock_path = Path(args[i + 1])
        except IndexError:
            print("pins: --lock needs a path", file=sys.stderr)
            return 2
        del args[i:i + 2]
    try:
        lock = load_lock(lock_path)
        if len(args) == 3 and args[0] == "check-clone":
            errs = check_clone(lock, args[1], Path(args[2]))
        elif len(args) == 2 and args[0] == "check-mvp-packages":
            errs = check_mvp_packages(lock, Path(args[1]))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except UsageError as e:
        print(f"pins: {e}", file=sys.stderr)
        return 2
    for e in errs:
        print(f"PIN MISMATCH {e}", file=sys.stderr)
    print(f"pins: {args[0]}: {'FAIL' if errs else 'OK'}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

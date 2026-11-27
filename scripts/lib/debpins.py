"""Build-host Debian package pins (ADR-0006; OSE-003 R03-5).

Reads upstream/debian/packages.lock.json and prints shell for the image builds:

  debpins.py install-line IMAGE   one line for a Dockerfile RUN: point apt at the
                                  snapshot, download each pinned .deb, check its
                                  SHA-256 against the lock BEFORE installing, then
                                  install it with the image's unhashed build packages
                                  (from the same snapshot) and verify the versions
  debpins.py verify-line IMAGE    one line that exits 1 unless every pinned package
                                  of IMAGE is installed at exactly its locked version
  debpins.py digest IMAGE         12 hex digits identifying the pin set of IMAGE
                                  (snapshot + packages); names the tools image tag
  debpins.py check                validate the lock file; RC 1 with messages if not

IMAGE is "hercules" (scripts/host/hercules-image.sh) or "tools" (scripts/smoke.sh).
The output is plain POSIX sh with no host-side expansion needed; it runs as root.
"""
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

LOCK = Path(__file__).resolve().parents[2] / "upstream" / "debian" / "packages.lock.json"
IMAGES = ("hercules", "tools")
PKG_KEYS = ("name", "image", "role", "version", "arch", "filename", "size", "sha256",
            "license_spdx", "license_evidence")


def load(path=LOCK):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(data):
    errs = []
    if data.get("schema_version") != 1:
        errs.append("schema_version must be 1")
    snap = data.get("snapshot", {})
    ts = snap.get("timestamp", "")
    if not re.fullmatch(r"\d{8}T\d{6}Z", ts):
        errs.append("snapshot.timestamp must look like 20261123T000000Z")
    for s in snap.get("sources", []):
        if not s.startswith("deb ") or f"snapshot.debian.org/archive/" not in s or f"/{ts} " not in s:
            errs.append(f"source is not on the pinned snapshot: {s}")
    if not snap.get("sources"):
        errs.append("snapshot.sources is empty")
    names = set()
    for p in data.get("packages", []):
        for k in PKG_KEYS:
            if k not in p:
                errs.append(f"{p.get('name', '?')}: missing {k}")
        n = p.get("name", "")
        if n in names:
            errs.append(f"{n}: duplicate")
        names.add(n)
        if p.get("image") not in IMAGES:
            errs.append(f"{n}: image must be one of {IMAGES}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(p.get("sha256", ""))):
            errs.append(f"{n}: sha256 must be 64 hex")
        if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", n):
            errs.append(f"{n}: not a Debian package name")
        if not re.fullmatch(r"[0-9A-Za-z.+~-]+", str(p.get("version", ""))):
            errs.append(f"{n}: unsupported version string (epochs need extra handling)")
        fn = str(p.get("filename", ""))
        if not fn.startswith("pool/") or Path(fn).name != f"{n}_{p.get('version')}_{p.get('arch')}.deb":
            errs.append(f"{n}: filename does not match name/version/arch")
    for img in IMAGES:
        for b in data.get("unhashed_build_packages", {}).get(img, []):
            if b in names:
                errs.append(f"{b}: listed both hashed and unhashed")
    return errs


def pinned(data, image):
    return [p for p in data["packages"] if p["image"] == image]


def verify_line(data, image):
    checks = []
    for p in pinned(data, image):
        n, v = p["name"], p["version"]
        checks.append(
            f'test "$(dpkg-query -W -f=\'${{Version}}\' {n} 2>/dev/null)" = {shlex.quote(v)} '
            f'|| {{ echo "debpins: {n} is not {v}" >&2; exit 1; }}')
    return " && ".join(checks) if checks else "true"


def install_line(data, image):
    pins = pinned(data, image)
    extra = data.get("unhashed_build_packages", {}).get(image, [])
    srcs = " ".join(shlex.quote(s) for s in data["snapshot"]["sources"])
    debs = " ".join(f"./{Path(p['filename']).name}" for p in pins)
    sums = " ".join(shlex.quote(f"{p['sha256']}  {Path(p['filename']).name}") for p in pins)
    parts = [
        "rm -f /etc/apt/sources.list.d/debian.sources",
        f"printf '%s\\n' {srcs} > /etc/apt/sources.list",
        "apt-get -o Acquire::Retries=5 update",
        "mkdir -p /tmp/debpins",
        "cd /tmp/debpins",
    ]
    if pins:
        parts += [
            "apt-get -o Acquire::Retries=5 download " + " ".join(f"{p['name']}={p['version']}" for p in pins),
            f"printf '%s\\n' {sums} | sha256sum -c -",
        ]
    parts += [
        "DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 install -y --no-install-recommends "
        + " ".join([debs, *extra]).strip(),
        "cd /",
        "rm -rf /tmp/debpins /var/lib/apt/lists/*",
        "{ " + verify_line(data, image) + "; }",
    ]
    return " && ".join(parts)


def digest(data, image):
    blob = json.dumps({"snapshot": data["snapshot"], "packages": pinned(data, image),
                       "unhashed": data.get("unhashed_build_packages", {}).get(image, [])},
                      sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    data = load()
    if argv[0] == "check":
        errs = check(data)
        for e in errs:
            print(f"debpins: {e}", file=sys.stderr)
        return 1 if errs else 0
    if len(argv) != 2 or argv[1] not in IMAGES:
        print(f"usage: debpins.py install-line|verify-line|digest {{{'|'.join(IMAGES)}}}", file=sys.stderr)
        return 2
    errs = check(data)
    if errs:
        print("debpins: lock invalid: " + "; ".join(errs), file=sys.stderr)
        return 1
    fn = {"install-line": install_line, "verify-line": verify_line, "digest": digest}.get(argv[0])
    if fn is None:
        print(f"debpins: unknown command {argv[0]}", file=sys.stderr)
        return 2
    print(fn(data, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

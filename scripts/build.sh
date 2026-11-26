#!/bin/sh
# OSE-004 host build: CC/370 toolchain in the ADR-0003 container, then hello.
# Usage: scripts/build.sh [toolchain|probes|hello|all]   (default: all)
# Exit codes: 0 ok, 1 build/verification failure, 2 usage, 3 blocked by an
# unapproved dependency (maclib370, see docs/research/2026-11-26-toolchain.md).
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CACHE="$ROOT/artifacts/cache/src"
OUT="$ROOT/artifacts/toolchain"
EVID="$ROOT/artifacts/evidence/ose-004"

# Pins: dependencies.lock.json (cc370, libc370, mbt) and ADR-0003 (image).
IMAGE_BASE="debian@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e"
IMAGE_TAG="ose-toolchain:ose004"
CC370_COMMIT=802dde1c43360b55c0d6ef371986e3b3f2fed0bb
LIBC370_COMMIT=fcde4e88b3bebca001355aa3c1dd3c3a633f04af
# maclib370 is required by cc370 >= 1.6.0 and libc370 >= 2.8.0 but is not in
# the lock. Until the human approves it, MACLIB370_COMMIT stays empty and the
# hello stage refuses to run.
MACLIB370_COMMIT=""

die() { echo "build.sh: $*" >&2; exit 1; }

fetch() { # name commit
    d="$CACHE/$1"
    if [ ! -d "$d/.git" ]; then
        git -c core.autocrlf=false clone -q "https://github.com/mvslovers/$1.git" "$d" || die "clone $1 failed"
        git -C "$d" config core.autocrlf false
    fi
    git -C "$d" -c core.autocrlf=false checkout -q "$2" || die "checkout $1@$2 failed"
    [ "$(git -C "$d" rev-parse HEAD)" = "$2" ] || die "$1 is not at pinned $2"
    [ -z "$(git -C "$d" status --porcelain)" ] || die "$1 working tree is not clean"
}

# Docker on Windows (Git Bash) needs a Windows path and no MSYS path rewriting.
hostpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else echo "$1"; fi; }
drun() {
    MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 \
        -v "$(hostpath "$ROOT"):/ose" -w /ose "$IMAGE_TAG" sh -euc "$1"
}

image() {
    MSYS_NO_PATHCONV=1 docker build -q -t "$IMAGE_TAG" - >/dev/null <<EOF || die "image build failed"
FROM $IMAGE_BASE
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev make python3 flex bison git \\
 && rm -rf /var/lib/apt/lists/* && useradd -u 1000 -m ose
EOF
}

toolchain() {
    fetch cc370 "$CC370_COMMIT"
    mkdir -p "$OUT" "$EVID"
    image
    drun '
        dpkg-query -W -f="\${Package}=\${Version}\n" gcc libc6-dev make python3 flex bison git > artifacts/evidence/ose-004/apt-versions.txt
        git config --global --add safe.directory /tmp/cc370
        rm -rf /tmp/cc370 && cp -a artifacts/cache/src/cc370 /tmp/cc370 && cd /tmp/cc370
        make -j"$(nproc)" tools compiler > /ose/artifacts/evidence/ose-004/cc370-build.log 2>&1
        make PREFIX=/ose/artifacts/toolchain install-tools install-compiler install-macros >> /ose/artifacts/evidence/ose-004/cc370-build.log 2>&1
        cd /ose/artifacts/toolchain
        { bin/cc370 --version | head -1; cc370/bin/as370 --version; cc370/bin/ld370 --version; } > /ose/artifacts/evidence/ose-004/versions.txt
    ' || die "toolchain build failed (log: artifacts/evidence/ose-004/cc370-build.log)"
    cat "$EVID/versions.txt"
}

probes() {
    fetch libc370 "$LIBC370_COMMIT"
    [ -f "$OUT/bin/cc370" ] || die "run 'scripts/build.sh toolchain' first"
    # PROBE_DIR: repo-relative directory of OSE-012 probe sources.
    pd=${PROBE_DIR:-tests/host/c-probes}
    ls "$ROOT/$pd"/p*.c >/dev/null 2>&1 || die "no probe sources in $pd"
    drun "pd=$pd"'
        out=artifacts/evidence/ose-004/probes; rm -rf $out; mkdir -p $out
        for p in $pd/p*.c; do
            n=$(basename $p .c)
            set +e
            artifacts/toolchain/bin/cc370 -S -O1 -I artifacts/cache/src/libc370/include \
                -o $out/$n.s $p > $out/$n.diag 2>&1
            rc=$?
            set -e
            echo "$n rc=$rc"
        done | tee $out/summary.txt
    '
}

hello() {
    fetch libc370 "$LIBC370_COMMIT"
    [ -f "$OUT/bin/cc370" ] || die "run 'scripts/build.sh toolchain' first"
    # Compile and assemble need only cc370's own prologue macros.
    drun '
        h=artifacts/evidence/ose-004/hello; mkdir -p $h
        artifacts/toolchain/bin/cc370 -S -O1 -I artifacts/cache/src/libc370/include -o $h/hello.s src/utils/hello/hello.c
        artifacts/toolchain/bin/cc370 -c -O1 -I artifacts/cache/src/libc370/include -o $h/hello.o src/utils/hello/hello.c
        sha256sum $h/hello.s $h/hello.o > $h/sha256.txt
        artifacts/toolchain/bin/file370 $h/hello.o > $h/file370.txt
    ' || die "hello compile failed"
    cat "$EVID/hello/sha256.txt"
    # Linking needs libc.a, and building libc370 >= 2.8.0 needs maclib370.
    [ -n "$MACLIB370_COMMIT" ] || { echo "build.sh: hello link blocked: maclib370 is not an approved dependency (OSE-004 handoff)" >&2; exit 3; }
    die "hello link stage not implemented until maclib370 is approved"
}

case "${1:-all}" in
    toolchain) toolchain ;;
    probes) probes ;;
    hello) hello ;;
    all) toolchain; probes; hello ;;
    *) echo "usage: $0 [toolchain|probes|hello|all]" >&2; exit 2 ;;
esac

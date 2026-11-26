#!/bin/sh
# OSE-004 host build: CC/370 toolchain in the ADR-0003 container, then hello.
# Usage: scripts/build.sh [toolchain|libc|probes|hello|all]   (default: all)
#   toolchain  cc370/as370/ld370 + libcc370rt from source, maclib370 into the sysroot
#   libc       libc370 built with that toolchain, installed into the sysroot
#   probes     OSE-012 C dialect probes (PROBE_DIR, compile only)
#   hello      compile, assemble and link src/utils/hello into a load module
#   all        toolchain, libc, hello (probes too when PROBE_DIR has sources)
# Exit codes: 0 ok, 1 build/verification failure, 2 usage.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
CACHE="$ROOT/artifacts/cache/src"
OUT="$ROOT/artifacts/toolchain"
EVID="$ROOT/artifacts/evidence/ose-004"

# Pins: dependencies.lock.json (cc370, libc370, maclib370) and ADR-0003 (image).
IMAGE_BASE="debian@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e"
IMAGE_TAG="ose-toolchain:ose004"
CC370_COMMIT=802dde1c43360b55c0d6ef371986e3b3f2fed0bb
LIBC370_COMMIT=fcde4e88b3bebca001355aa3c1dd3c3a633f04af
MACLIB370_COMMIT=e85286a7cb994eae4003143eba693ab7931b026e   # approved 2026-11-26

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
# as370 stamps &SYSDATE/&SYSTIME into objects (libc370 @@CRTSVC, @@CTHRD).
# Fix them to the libc370 pin's commit time so libc.a and HELLO reproduce.
ASMDATE=10/21/26
ASMTIME=13.55
# ld370 stamps the LKED IDR and the XMIT INMFTIME: same instant, YYDDD/HHMMSS.
LDDATE=26294
LDTIME=135500
drun() {
    MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 \
        -e ASMDATE="$ASMDATE" -e ASMTIME="$ASMTIME" \
        -e LDDATE="$LDDATE" -e LDTIME="$LDTIME" \
        -e PATH=/ose/artifacts/toolchain/bin:/usr/local/bin:/usr/bin:/bin \
        -v "$(hostpath "$ROOT"):/ose" -w /ose "$IMAGE_TAG" sh -euc "$1"
}
need_toolchain() { [ -f "$OUT/bin/cc370" ] || die "run 'scripts/build.sh toolchain' first"; }

image() {
    MSYS_NO_PATHCONV=1 docker build -q -t "$IMAGE_TAG" - >/dev/null <<EOF || die "image build failed"
FROM $IMAGE_BASE
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev make python3 flex bison git \\
 && rm -rf /var/lib/apt/lists/* && useradd -u 1000 -m ose
EOF
}

toolchain() {
    fetch cc370 "$CC370_COMMIT"
    fetch maclib370 "$MACLIB370_COMMIT"
    mkdir -p "$OUT" "$EVID"
    image
    drun '
        e=/ose/artifacts/evidence/ose-004
        dpkg-query -W -f="\${Package}=\${Version}\n" gcc libc6-dev make python3 flex bison git > $e/apt-versions.txt
        # From /, not /ose: in a Git worktree /ose/.git names a host path the
        # container cannot resolve, and git dies looking for a repository.
        (cd / && git config --global --add safe.directory /tmp/cc370)
        rm -rf /tmp/cc370 && cp -a artifacts/cache/src/cc370 /tmp/cc370 && cd /tmp/cc370
        make -j"$(nproc)" tools compiler runtime > $e/cc370-build.log 2>&1
        make PREFIX=/ose/artifacts/toolchain install-tools install-compiler install-macros install-runtime >> $e/cc370-build.log 2>&1
        # maclib370 checkout -> <sysroot>/maclib370/macros, where as370 looks (cc370 README).
        cd /ose/artifacts/cache/src/maclib370
        python3 -I tools/extract.py --verify > $e/maclib370-verify.txt
        m=/ose/artifacts/toolchain/cc370/maclib370/macros
        rm -rf $m && mkdir -p $m && cp maclib/*.macro amodgen/*.macro $m/
        ls $m | wc -l > $e/maclib370-count.txt
        cd /ose/artifacts/toolchain
        { bin/cc370 --version | head -1; cc370/bin/as370 --version; cc370/bin/ld370 --version; } > $e/versions.txt
    ' || die "toolchain build failed (logs: artifacts/evidence/ose-004/)"
    cat "$EVID/versions.txt" "$EVID/maclib370-verify.txt"
}

libc() {
    fetch libc370 "$LIBC370_COMMIT"
    need_toolchain
    drun '
        e=/ose/artifacts/evidence/ose-004
        rm -rf /tmp/libc && cp -a artifacts/cache/src/libc370 /tmp/libc && cd /tmp/libc
        MACLIB370=/ose/artifacts/toolchain/cc370/maclib370 make install > $e/libc370-build.log 2>&1
        sha256sum /ose/artifacts/toolchain/cc370/lib/libc.a > $e/libc-sha256.txt
    ' || die "libc370 build failed (log: artifacts/evidence/ose-004/libc370-build.log)"
    cat "$EVID/libc-sha256.txt"
}

probes() {
    need_toolchain
    # PROBE_DIR: repo-relative directory of OSE-012 probe sources.
    pd=${PROBE_DIR:-tests/host/c-probes}
    ls "$ROOT/$pd"/p*.c >/dev/null 2>&1 || die "no probe sources in $pd"
    drun "pd=$pd"'
        out=artifacts/evidence/ose-004/probes; rm -rf $out; mkdir -p $out
        for p in $pd/p*.c; do
            n=$(basename $p .c)
            set +e
            cc370 -S -O1 -o $out/$n.s $p > $out/$n.diag 2>&1
            rc=$?
            set -e
            echo "$n rc=$rc"
        done | tee $out/summary.txt
    '
}

hello() {
    need_toolchain
    [ -f "$OUT/cc370/lib/libc.a" ] || die "run 'scripts/build.sh libc' first"
    drun '
        h=artifacts/evidence/ose-004/hello; rm -rf $h; mkdir -p $h
        cc370 -S -O1 -o $h/hello.s src/utils/hello/hello.c
        cc370 -c -O1 -o $h/hello.o src/utils/hello/hello.c
        cc370 -O1 -o $h/HELLO src/utils/hello/hello.c -flinker-output=xmit > $h/link.log 2>&1
        sha256sum $h/hello.s $h/hello.o $h/HELLO $h/HELLO.xmit > $h/sha256.txt
        file370 -v $h/hello.o > $h/file370-obj.txt
        file370 -v $h/HELLO > $h/file370-lmod.txt
        file370 -v $h/HELLO.xmit > $h/file370-xmit.txt
    ' || die "hello build failed (see artifacts/evidence/ose-004/hello/)"
    cat "$EVID/hello/sha256.txt"
}

case "${1:-all}" in
    toolchain) toolchain ;;
    libc) libc ;;
    probes) probes ;;
    hello) hello ;;
    all) toolchain; libc
         if ls "$ROOT/${PROBE_DIR:-tests/host/c-probes}"/p*.c >/dev/null 2>&1; then probes; fi
         hello ;;
    *) echo "usage: $0 [toolchain|libc|probes|hello|all]" >&2; exit 2 ;;
esac

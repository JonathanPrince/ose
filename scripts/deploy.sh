#!/bin/sh
# OSE-004 guest acceptance 2-4 against the leased DASD volume.
# Usage: scripts/deploy.sh [deploy|run|all]
#   deploy  IPL, stage HELLO.xmit through the EBCDIC reader, RECEIVE it into
#           <user>.OSE.LOAD, confirm it with a separate listing job, shutdown (2)
#   run     IPL, batch job (step RC = PARM: 0 and 4, output from spool),
#           TSO CALL of the same module, shutdown                           (3, 4)
#   all     deploy, then run (default)
# Needs: make build (artifacts/evidence/ose-004/hello/HELLO.xmit), the OSE-003
# image and a sysgen'd volume (DASD_VOLUME). Evidence:
# artifacts/evidence/ose-004/guest/runs/<UTC>-<pid>/<mode>/. Exit 0 only if every check passed.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/lib/common.sh"
NAME=ose-hello
XMIT="$ROOT/artifacts/evidence/ose-004/hello/HELLO.xmit"
XMIT_SHA256=0e69e9fa44689fc49a27541084f9cd77ff715f761772a3c98e664529857d0d9f   # runbook hello-compile-deploy
# one new directory per invocation; earlier evidence is never overwritten
OUT="$ROOT/artifacts/evidence/ose-004/guest/runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
[ ! -e "$OUT" ] || die "$OUT exists"
GUEST_EV=/work/evidence/ose-004

check_xmit() {
    [ -f "$XMIT" ] || die "no $XMIT: run make build first"
    got=$("$PY" -I -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$XMIT")
    [ "$got" = "$XMIT_SHA256" ] || die "HELLO.xmit sha256 $got is not the recorded build $XMIT_SHA256"
}

guest() { # mode, extra args for hello_guest.py
    mode=$1; shift
    tools_image
    creds_line=$(creds) || die "cannot read guest credentials from $DASD_VOLUME"
    u=${creds_line%% *}; p=${creds_line#* }
    [ -n "$u" ] && [ -n "$p" ] && [ "$u" != "$p" ] || die "no MVSCE02 entry in users.conf"
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    MSYS_NO_PATHCONV=1 docker run -d --name "$NAME" --user 1000:1000 \
        -e GUEST_USER="$u" -e GUEST_PASS="$p" \
        -v "$(hostpath "$ROOT"):/ose:ro" -v "$DASD_VOLUME:/work" -w /work/sysgen/MVSCE "$TOOLS_IMAGE" \
        sh -c 'rm -rf "$0" && exec python3 -I /ose/tests/guest/hello/hello_guest.py --evidence "$0" "$@"' \
        "$GUEST_EV/$mode" --mode "$mode" "$@" >/dev/null
    log "started $NAME ($mode) on $DASD_VOLUME"
    rc=$(docker wait "$NAME")
    mkdir -p "$OUT/$mode"
    docker logs "$NAME" > "$OUT/$mode/console.txt" 2>&1 || true
    docker rm "$NAME" >/dev/null 2>&1 || true
    MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work:ro" -v "$(hostpath "$OUT"):/out" "$HERC_IMAGE" \
        sh -c "cp -R $GUEST_EV/$mode/. /out/$mode/" || true
    sed "s/$p/<redacted>/g" "$OUT/$mode/console.txt" > "$OUT/$mode/console.tmp" && mv "$OUT/$mode/console.tmp" "$OUT/$mode/console.txt"
    cat "$OUT/$mode/console.txt"
    return "$rc"
}

case "${1:-all}" in
    deploy) check_xmit; guest deploy --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit ;;
    run)    guest run ;;
    all)    check_xmit; guest deploy --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit && guest run ;;
    *) echo "usage: $0 [deploy|run|all]" >&2; exit 2 ;;
esac

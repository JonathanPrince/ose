#!/bin/sh
# OSE-004 guest acceptance 2-4 against the leased DASD volume.
# Usage: scripts/deploy.sh [deploy|run|all|stale]
#   deploy  IPL, stage HELLO.xmit through the EBCDIC reader, RECEIVE it into
#           <user>.OSE.LOAD, confirm it with a separate listing job, shutdown (2)
#   run     IPL, batch job (step RC = PARM: 0 and 4, output from spool),
#           TSO CALL of the same module, shutdown                           (3, 4)
#   all     deploy, then run (default)
#   stale   negative test (review R04-2): with the target library present and not
#           deleted, step GONE must stop STAGE, RECV and CLEANUP
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
OUT="${OSE004_EVIDENCE_ROOT:-$ROOT/artifacts/evidence/ose-004/guest}/runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
[ ! -e "$OUT" ] || die "$OUT exists"
RUN_ID=${OUT##*/}
GUEST_EV=/work/evidence/ose-004/runs/$RUN_ID   # the guest copy, one per invocation too
# sha256 and relative path of every file under a directory, sorted (host and container)
MANIFEST='import hashlib,os,sys
r=sys.argv[1]; out=[]
for d,_,fs in os.walk(r):
    for f in fs:
        p=os.path.join(d,f); rel=os.path.relpath(p,r).replace(os.sep,"/")
        if rel!="console.txt": out.append(hashlib.sha256(open(p,"rb").read()).hexdigest()+"  "+rel)
sys.stdout.buffer.write(("\n".join(sorted(out)) + "\n").encode())'   # LF on every OS (print gives CRLF on Windows)

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
        sh -c '[ ! -e "$0" ] && mkdir -p "$0" && exec python3 -I /ose/tests/guest/hello/hello_guest.py --evidence "$0" "$@"' \
        "$GUEST_EV/$mode" --mode "$mode" "$@" >/dev/null
    log "started $NAME ($mode) on $DASD_VOLUME"
    rc=$(docker wait "$NAME") || { log "docker wait failed"; return 1; }
    mkdir -p "$OUT/$mode"
    if ! docker logs "$NAME" > "$OUT/$mode/console.txt" 2>&1; then
        log "EVIDENCE: docker logs failed; container $NAME kept"; return 1
    fi
    docker rm "$NAME" >/dev/null 2>&1 || true
    sed "s/$p/<redacted>/g" "$OUT/$mode/console.txt" > "$OUT/$mode/console.tmp" && mv "$OUT/$mode/console.tmp" "$OUT/$mode/console.txt"
    cat "$OUT/$mode/console.txt"
    export_evidence "$mode" || return 1
    return "$rc"
}

# R04-3: copy the guest's evidence to the host and prove the copy complete
# (same sha256 manifest on both sides) before the guest copy is deleted. Any
# failure returns nonzero, even when the guest checks passed, and keeps the
# guest copy in the volume for a retry.
export_evidence() {
    m=$1
    MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work:ro" -v "$(hostpath "$OUT"):/out" "$HERC_IMAGE" \
        sh -c 'test -d "$0" && cp -R "$0/." "/out/$1/"' "$GUEST_EV/$m" "$m" \
        || { log "EVIDENCE: export of $GUEST_EV/$m failed; guest copy kept in $DASD_VOLUME"; return 1; }
    want=$(MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work:ro" "$HERC_IMAGE" python3 -I -c "$MANIFEST" "$GUEST_EV/$m") \
        || { log "EVIDENCE: cannot hash the guest copy; kept in $DASD_VOLUME"; return 1; }
    got=$("$PY" -I -c "$MANIFEST" "$OUT/$m") || { log "EVIDENCE: cannot hash $OUT/$m"; return 1; }
    if [ -z "$want" ] || [ "$want" != "$got" ]; then
        log "EVIDENCE: host copy $OUT/$m differs from the guest copy (or is empty); guest copy kept in $DASD_VOLUME:$GUEST_EV/$m"
        return 1
    fi
    log "evidence exported and verified ($(printf '%s\n' "$want" | wc -l | tr -d ' ') files): $OUT/$m"
    MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 -v "$DASD_VOLUME:/work" "$HERC_IMAGE" rm -rf "$GUEST_EV/$m" \
        || log "note: guest copy $GUEST_EV/$m could not be removed (harmless; the host copy is verified)"
}

case "${1:-all}" in
    deploy) check_xmit; guest deploy --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit ;;
    run)    guest run ;;
    stale)  check_xmit; guest deploy-stale --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit ;;   # R04-2 negative test
    all)    check_xmit; guest deploy --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit && guest run ;;
    *) echo "usage: $0 [deploy|run|all|stale]" >&2; exit 2 ;;
esac

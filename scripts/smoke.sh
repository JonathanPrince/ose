#!/bin/sh
# OSE-003 tests 3-5 against the sysgen result in the leased DASD volume.
# Usage: scripts/smoke.sh [ipl1|ipl2|all]
#   ipl1  cold IPL, wait for $HASP099, clean shutdown                (test 3)
#   ipl2  cold IPL, JES2 smoke job with RC check, TSO smoke, shutdown (tests 3-5)
# Evidence: a new directory per invocation, artifacts/evidence/ose-003/smoke-runs/<UTC>-<pid>/
# (never an existing one). Exit 0 only if every check passed.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/lib/common.sh"
NAME=ose-smoke
SMOKE_EV=/work/evidence/smoke
run_ipl() { # tag, extra args for mvs-smoke.py
    tag=$1; shift
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    # shellcheck disable=SC2086
    MSYS_NO_PATHCONV=1 docker run -d --name "$NAME" --user 1000:1000 \
        -v "$(hostpath "$ROOT"):/ose:ro" -v "$DASD_VOLUME:/work" -w /work/sysgen/MVSCE "$TOOLS_IMAGE" \
        python3 -I /ose/scripts/lib/mvs-smoke.py --mvsce /work/sysgen/MVSCE --evidence "$SMOKE_EV" --tag "$tag" "$@" >/dev/null
}

finish() { # tag -> rc
    rc=$(docker wait "$NAME")
    docker logs "$NAME" > "$RUN_OUT/smoke-$1-console.txt" 2>&1 || true
    cat "$RUN_OUT/smoke-$1-console.txt"
    return "$rc"
}

export_ev() {
    mkdir -p "$RUN_OUT/smoke"
    MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work:ro" -v "$(hostpath "$RUN_OUT"):/out" "$HERC_IMAGE" \
        sh -c 'cp -a /work/evidence/smoke/. /out/smoke/ 2>/dev/null; cp /work/sysgen/MVSCE/printers/prt00e.txt /out/smoke/prt00e.txt 2>/dev/null; true'
}

ipl1() { tools_image; run_ipl ipl1; finish ipl1; }

ipl2() {
    tools_image
    set -- $(creds); u=$1; p=$2
    # R03-4: the handshake files are named by a per-invocation run ID, and
    # mvs-smoke.py deletes every older ipl2 marker before Hercules starts.
    run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
    ready="$SMOKE_EV/ipl2-$run_id-ready"; done_f="$SMOKE_EV/ipl2-$run_id-tso-done"
    run_ipl ipl2 --jes2 /ose/jcl/smoke/jes2-smoke.jcl --expect BR14=0000,PLANT=0004 \
        --user "$u" --password "$p" --hold-for-tso 900 --run-id "$run_id"
    # wait until MVS is up and the JES2 check is done, then run the TSO smoke
    i=0
    until MSYS_NO_PATHCONV=1 docker exec "$NAME" test -f "$ready" 2>/dev/null; do
        i=$((i + 1)); [ $i -lt 600 ] || break
        docker ps -q --filter "name=$NAME" --filter status=running | grep -q . || break
        sleep 3
    done
    tso_rc=1
    if MSYS_NO_PATHCONV=1 docker exec "$NAME" test -f "$ready" 2>/dev/null; then
        set +e
        MSYS_NO_PATHCONV=1 docker exec -e TSO_USER="$u" -e TSO_PASS="$p" "$NAME" \
            python3 -I /ose/scripts/lib/tso-smoke.py --evidence "$SMOKE_EV"
        tso_rc=$?
        set -e
        MSYS_NO_PATHCONV=1 docker exec "$NAME" touch "$done_f"
    fi
    set +e; finish ipl2; ipl_rc=$?; set -e
    echo "ipl2: mvs-smoke rc=$ipl_rc tso-smoke rc=$tso_rc"
    [ "$ipl_rc" -eq 0 ] && [ "$tso_rc" -eq 0 ]
}

# Evidence never overwrites earlier evidence (2026-11-27: a fixed export
# directory let an OSE-004 regression run overwrite OSE-003's checksummed
# smoke files). Each invocation exports to a directory that must not exist
# yet, and the volume's own smoke directory is emptied first, so files left
# by earlier runs are not exported as this run's.
RUN_OUT="$EVID/smoke-runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
[ ! -e "$RUN_OUT" ] || die "$RUN_OUT exists"
mkdir -p "$RUN_OUT"
MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 -v "$DASD_VOLUME:/work" "$HERC_IMAGE" \
    sh -c 'rm -rf /work/evidence/smoke && mkdir -p /work/evidence/smoke' || die "cannot reset /work/evidence/smoke in $DASD_VOLUME"
log "evidence: $RUN_OUT"
case "${1:-all}" in
    ipl1) ipl1; rc=$? ;;
    ipl2) set +e; ipl2; rc=$?; set -e ;;
    all)  set +e; ipl1; r1=$?; ipl2; r2=$?; set -e; rc=$((r1 | r2)) ;;
    *) echo "usage: $0 [ipl1|ipl2|all]" >&2; exit 2 ;;
esac
export_ev
exit "$rc"

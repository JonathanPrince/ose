#!/bin/sh
# OSE-003 tests 3-5 against the sysgen result in the leased DASD volume.
# Usage: scripts/smoke.sh [ipl1|ipl2|all]
#   ipl1  cold IPL, wait for $HASP099, clean shutdown                (test 3)
#   ipl2  cold IPL, JES2 smoke job with RC check, TSO smoke, shutdown (tests 3-5)
# Evidence: artifacts/evidence/ose-003/smoke/. Exit 0 only if every check passed.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/lib/common.sh"
NAME=ose-smoke
SMOKE_EV=/work/evidence/smoke
PY=${PYTHON:-$(command -v python3 2>/dev/null || command -v python)}
DEBPINS="$PY -I $ROOT/scripts/lib/debpins.py"
# R03-5 / ADR-0006 (proposed): the tools layer adds s3270 and netbase, pinned by
# version and .deb SHA-256 in upstream/debian/packages.lock.json. The tag names
# the pin set, and the installed versions are re-checked on every use, so an
# older or hand-built image with the same name is never trusted.
TOOLS_IMAGE="${HERC_IMAGE}-tools-$($DEBPINS digest tools)" || die "debpins: lock invalid"

tools_image() {
    if ! docker image inspect "$TOOLS_IMAGE" >/dev/null 2>&1; then
        log "building $TOOLS_IMAGE (s3270 and netbase pinned by upstream/debian/packages.lock.json)"
        apt_run=$($DEBPINS install-line tools) || die "debpins: lock invalid"
        MSYS_NO_PATHCONV=1 docker build -q -t "$TOOLS_IMAGE" - >/dev/null <<EOF || die "tools image build failed"
FROM $HERC_IMAGE
USER root
RUN $apt_run
USER ose
EOF
    fi
    verify=$($DEBPINS verify-line tools) || die "debpins: lock invalid"
    MSYS_NO_PATHCONV=1 docker run --rm "$TOOLS_IMAGE" sh -c "$verify" \
        || die "$TOOLS_IMAGE does not carry the pinned tool packages"
    MSYS_NO_PATHCONV=1 docker run --rm "$TOOLS_IMAGE" sh -c "$($DEBPINS verify-line hercules)" \
        || die "$TOOLS_IMAGE does not carry the pinned Hercules-image packages"
}

# Non-admin user for the JES2 job and TSO: from upstream users.conf in the
# volume (sysgen's published defaults), never stored in this repository.
creds() {
    MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work:ro" "$HERC_IMAGE" \
        awk '$1 == "MVSCE02" {print $1, $2}' /work/sysgen/users.conf
}

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
    docker logs "$NAME" > "$EVID/smoke-$1-console.txt" 2>&1 || true
    cat "$EVID/smoke-$1-console.txt"
    return "$rc"
}

export_ev() {
    mkdir -p "$EVID/smoke"
    MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work:ro" -v "$(hostpath "$EVID"):/out" "$HERC_IMAGE" \
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

mkdir -p "$EVID"
case "${1:-all}" in
    ipl1) ipl1; rc=$? ;;
    ipl2) set +e; ipl2; rc=$?; set -e ;;
    all)  set +e; ipl1; r1=$?; ipl2; r2=$?; set -e; rc=$((r1 | r2)) ;;
    *) echo "usage: $0 [ipl1|ipl2|all]" >&2; exit 2 ;;
esac
export_ev
exit "$rc"

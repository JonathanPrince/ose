#!/bin/sh
# OSE-003: pinned MVS/CE sysgen in the ADR-0003 container.
# Usage: scripts/sysgen.sh [run|status|export|negative-pin]
#   run           start (or continue) the sysgen in the leased DASD volume, wait, export
#   status        show the container state and the last wrapper log lines
#   export        copy MVSCE/ (DASD, conf) and evidence from the volume to artifacts/
#   negative-pin  test 7: restart from step 9 with a wrong MVP pin; must fail before install
# Exit codes: 0 ok, 1 failure, 2 usage, 10 pin validation failed (sysgen not started),
#             20 sysgen failed after ATTEMPTS, 30 post-run pin check failed.
# The run happens in a Docker volume, not on the Windows bind mount: Hercules
# DASD I/O through Docker Desktop's file sharing is slow, and NTFS is not the
# file system sysgen was written for.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/lib/common.sh"
NAME=$(guest_container ose-sysgen-run)   # per volume (OSE-009)
OUTDIR="$ROOT/artifacts/sysgen"

prepare() {
    fetch sysgen https://github.com/MVS-sysgen/sysgen.git "$SYSGEN_COMMIT"
    docker image inspect "$HERC_IMAGE" >/dev/null 2>&1 || die "image $HERC_IMAGE missing: run scripts/host/hercules-image.sh"
    docker volume inspect "$DASD_VOLUME" >/dev/null 2>&1 || {
        docker volume create "$DASD_VOLUME" >/dev/null
        # the volume root belongs to root; hand it to uid 1000 once
        MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work" "$HERC_IMAGE" sh -c 'chown 1000:1000 /work' 2>/dev/null \
            || MSYS_NO_PATHCONV=1 docker run --rm --user 0 -v "$DASD_VOLUME:/work" "$HERC_IMAGE" chown 1000:1000 /work
        log "created DASD volume $DASD_VOLUME"
    }
}

start() { # extra env as KEY=VALUE args
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    envs=""
    for kv in "$@"; do envs="$envs -e $kv"; done
    # shellcheck disable=SC2086
    MSYS_NO_PATHCONV=1 docker run -d --name "$NAME" --user 1000:1000 \
        -e SYSGEN_COMMIT="$SYSGEN_COMMIT" -e RAKF_COMMIT="$RAKF_COMMIT" -e MVP_COMMIT="$MVP_COMMIT" $envs \
        -v "$(hostpath "$ROOT"):/ose:ro" -v "$DASD_VOLUME:/work" -w /work \
        "$HERC_IMAGE" bash /ose/scripts/lib/sysgen-in-container.sh >/dev/null
    log "started container $NAME"
}

wait_rc() {
    rc=$(docker wait "$NAME")
    docker logs "$NAME" > "$EVID/container-$1.log" 2>&1 || true
    echo "$rc"
}

export_out() {
    mkdir -p "$OUTDIR" "$EVID"
    MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 -v "$DASD_VOLUME:/work:ro" -v "$(hostpath "$OUTDIR"):/out" \
        "$HERC_IMAGE" sh -c 'rm -rf /out/MVSCE /out/evidence; [ -d /work/sysgen/MVSCE ] && cp -a /work/sysgen/MVSCE /out/; cp -a /work/evidence /out/'
    cp -f "$OUTDIR"/evidence/* "$EVID"/ 2>/dev/null || true
    ( cd "$EVID" && sha256sum ./*.log ./*.txt 2>/dev/null > SHA256SUMS || true )
    log "exported to artifacts/sysgen (MVSCE/, evidence/) and artifacts/evidence/ose-003"
}

case "${1:-run}" in
    run)
        guest_lease_begin            # OSE-009: exclusive use of $DASD_VOLUME
        mkdir -p "$EVID"; prepare
        t0=$(date +%s); start ATTEMPTS="${ATTEMPTS:-3}" TIMEOUT="${TIMEOUT:-3600}"
        rc=$(wait_rc run); t1=$(date +%s)
        echo "sysgen run rc=$rc elapsed=$((t1 - t0))s" | tee "$EVID/run-summary.txt"
        export_out
        exit "$rc" ;;
    status)
        docker ps -a --filter "name=$NAME" --format '{{.Names}} {{.Status}}'
        MSYS_NO_PATHCONV=1 docker run --rm -v "$DASD_VOLUME:/work:ro" "$HERC_IMAGE" sh -c 'tail -5 /work/evidence/wrapper.log; tail -3 /work/sysgen/sysgen.log 2>/dev/null' ;;
    export) export_out ;;
    negative-pin)
        guest_lease_begin            # OSE-009: the source volume
        # On a copy of the leased volume: a --step restart restores step-8 DASD,
        # which must not touch the finished system.
        mkdir -p "$EVID"; prepare
        NEG="${DASD_VOLUME}-negpin"
        docker volume rm -f "$NEG" >/dev/null 2>&1 || true
        docker volume create "$NEG" >/dev/null
        MSYS_NO_PATHCONV=1 docker run --rm --user 0 -v "$DASD_VOLUME:/from:ro" -v "$NEG:/to" "$HERC_IMAGE" \
            sh -c 'cp -a /from/. /to/ && chown -R 1000:1000 /to && rm -rf /to/evidence'
        DASD_VOLUME=$NEG
        start ATTEMPTS=1 TIMEOUT="${TIMEOUT:-3600}" MVP_PIN_OVERRIDE=0000000000000000000000000000000000000000 \
            CONTINUE_FLAG= SYSGEN_STEP=step_09_mvp
        rc=$(wait_rc negative-pin)
        MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 -v "$NEG:/work:ro" -v "$(hostpath "$EVID"):/out" "$HERC_IMAGE" \
            sh -c 'mkdir -p /out/negative-pin && cp -a /work/evidence/. /out/negative-pin/'
        echo "negative-pin rc=$rc" | tee "$EVID/negative-pin-summary.txt"
        [ "$rc" -ne 0 ] || die "negative-pin: sysgen succeeded with a wrong MVP pin" ;;
    *) echo "usage: $0 [run|status|export|negative-pin]" >&2; exit 2 ;;
esac

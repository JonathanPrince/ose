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
XMIT="$ROOT/artifacts/evidence/ose-004/hello/HELLO.xmit"
XMIT_SHA256=0e69e9fa44689fc49a27541084f9cd77ff715f761772a3c98e664529857d0d9f   # runbook hello-compile-deploy
# one new directory per invocation; earlier evidence is never overwritten
OUT="${OSE004_EVIDENCE_ROOT:-$ROOT/artifacts/evidence/ose-004/guest}/runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
[ ! -e "$OUT" ] || die "$OUT exists"
RUN_ID=${OUT##*/}
GUEST_EV=/work/evidence/ose-004/runs/$RUN_ID   # the guest copy, one per invocation too
case "${1:-all}" in deploy|run|stale|all) guest_lease_begin ;; esac   # OSE-009
check_xmit() {
    [ -f "$XMIT" ] || die "no $XMIT: run make build first"
    got=$("$PY" -I -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$XMIT")
    [ "$got" = "$XMIT_SHA256" ] || die "HELLO.xmit sha256 $got is not the recorded build $XMIT_SHA256"
}

guest() { # mode, extra args for hello_guest.py
    m=$1; shift
    guest_run ose-hello /ose/tests/guest/hello/hello_guest.py "$m" --mode "$m" "$@"
}

case "${1:-all}" in
    deploy) check_xmit; guest deploy --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit ;;
    run)    guest run ;;
    stale)  check_xmit; guest deploy-stale --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit ;;   # R04-2 negative test
    all)    check_xmit; guest deploy --xmit /ose/artifacts/evidence/ose-004/hello/HELLO.xmit && guest run ;;
    *) echo "usage: $0 [deploy|run|all|stale]" >&2; exit 2 ;;
esac

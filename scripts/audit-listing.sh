#!/bin/sh
# OSE-011 acceptance 2: run the read-only name-collision listing job
# (jcl/audit/list-libraries.jcl) on the leased DASD volume as MVSCE02, parse
# its RCs and member lists, and export the evidence verified.
# Usage: scripts/audit-listing.sh       (DASD_VOLUME selects the volume)
# Evidence: artifacts/evidence/ose-011/guest/runs/<UTC>-<pid>/listing/
# Exit 0 only if the job RCs were as expected, the spool was parsed, the
# shutdown was clean and the evidence export was verified. A name collision
# is a finding in listing-result.json, not a failure.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/lib/common.sh"
OUT="${OSE011_EVIDENCE_ROOT:-$ROOT/artifacts/evidence/ose-011/guest}/runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
[ ! -e "$OUT" ] || die "$OUT exists"
GUEST_EV=/work/evidence/ose-011/runs/${OUT##*/}
guest_run ose-audit /ose/tests/guest/audit/run_listing.py listing

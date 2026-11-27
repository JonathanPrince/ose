#!/bin/sh
# OSE-009 acceptance tests 2-4 on disposable guest volumes, end to end.
# Usage: tests/integration/harness/recovery.sh
#   SRC_VOLUME   source of the baseline snapshot (default ose-sysgen-1; only read)
#   VOL_A, VOL_B the two disposable guests (default ose-h009-a, ose-h009-b; replaced)
#   PORT_A, PORT_B host TN3270 ports for test 2 (default 13270, 13271; 127.0.0.1 only)
# Steps:
#   0. snapshot SRC_VOLUME as the baseline; restore it into VOL_A and VOL_B (--create)
#   2. both guests run the OSE-003 JES2/TSO smoke at the same time, each with TN3270
#      published on its own host port; both ports answer while both run
#   3. on VOL_A: IPL, create a marker data set, kill -9 Hercules; the marker survived
#      the kill (check present); restore the baseline; smoke passes; marker absent
#   4. a copy of the baseline with one flipped byte is refused by restore, and
#      VOL_A is left exactly as it was
# Evidence: artifacts/evidence/ose-009/runs/<UTC>-<pid>/ (summary.txt, logs, guest
# evidence exported verified). Exit 0 only if every step passed.
set -eu
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
. "$ROOT/scripts/lib/common.sh"
SRC=${SRC_VOLUME:-ose-sysgen-1}
A=${VOL_A:-ose-h009-a}
B=${VOL_B:-ose-h009-b}
PORT_A=${PORT_A:-13270}
PORT_B=${PORT_B:-13271}
RUN=$(date -u +%Y%m%dT%H%M%SZ)-$$
OUT="${OSE009_EVIDENCE_ROOT:-$ROOT/artifacts/evidence/ose-009}/runs/$RUN"
[ ! -e "$OUT" ] || die "$OUT exists"
mkdir -p "$OUT"
SNAP="h009-base-$(echo "$RUN" | tr 'A-Z' 'a-z')"
GPY() { "$PY" -I "$GUEST_PY" "$@"; }
step() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }
result() { echo "RESULT $*" | tee -a "$OUT/summary.txt"; }
fails=0
check() { # name rc-expected rc-got
    if [ "$2" = "$3" ]; then result "$1: ok (rc $3)"; else result "$1: FAIL (expected rc $2, got $3)"; fails=$((fails + 1)); fi
}

# Leases through the shared functions (R09-4): every container this run or its
# child scripts start carries its lease's label, and on exit, normal or not, the
# leases are released only after those containers are stopped and confirmed gone.
export OSE_TASK=OSE-009-recovery
MNAME=

volume_manifest() { # sha256 of every guest file in a volume (to show it is unchanged)
    MSYS_NO_PATHCONV=1 docker run --rm -v "$1:/work:ro" "$HERC_IMAGE" sh -c \
        'cd /work && find sysgen/MVSCE sysgen/users.conf -type f | LC_ALL=C sort | xargs sha256sum' | sha256sum | cut -c1-64
}

# --- 0. baseline snapshot and two disposable guests ----------------------------
step "0: lease $SRC, $A, $B"
guest_lease_begin "$SRC"; TOK_SRC=$(lease_token "$SRC")   # acquire refuses a volume with running containers
guest_lease_begin "$A";   TOK_A=$(lease_token "$A")
guest_lease_begin "$B";   TOK_B=$(lease_token "$B")
step "0: snapshot $SRC -> $SNAP"
GPY snapshot create --volume "$SRC" --name "$SNAP" --token "$TOK_SRC" --note "OSE-009 recovery baseline" \
    > "$OUT/t0-snapshot.txt" 2>&1 || { cat "$OUT/t0-snapshot.txt"; die "snapshot failed"; }
cat "$OUT/t0-snapshot.txt" >> "$OUT/summary.txt"
for v in "$A" "$B"; do
    docker volume rm "$v" >/dev/null 2>&1 || true          # disposable: always start from the snapshot
    step "0: restore $SNAP -> $v (new volume)"
    [ "$v" = "$A" ] && t=$TOK_A || t=$TOK_B
    GPY restore --volume "$v" --name "$SNAP" --token "$t" --create > "$OUT/t0-restore-$v.txt" 2>&1 \
        || { cat "$OUT/t0-restore-$v.txt"; die "restore into $v failed"; }
    cat "$OUT/t0-restore-$v.txt" >> "$OUT/summary.txt"
done

# --- 2. two guests at the same time on different ports --------------------------
step "2: smoke on $A (TN3270 127.0.0.1:$PORT_A) and $B (127.0.0.1:$PORT_B) concurrently"
( DASD_VOLUME=$A OSE_LEASE_TOKEN=$TOK_A GUEST_TN3270_PORT=$PORT_A sh "$ROOT/scripts/smoke.sh" all \
    > "$OUT/t2-smoke-a.txt" 2>&1; echo $? > "$OUT/t2-smoke-a.rc" ) &
pa=$!
( DASD_VOLUME=$B OSE_LEASE_TOKEN=$TOK_B GUEST_TN3270_PORT=$PORT_B sh "$ROOT/scripts/smoke.sh" all \
    > "$OUT/t2-smoke-b.txt" 2>&1; echo $? > "$OUT/t2-smoke-b.rc" ) &
pb=$!
# while both run: both containers up at once, and both host ports answer with TN3270 data
"$PY" -I - "$PORT_A" "$PORT_B" ose-smoke "$A" "$B" > "$OUT/t2-probe.txt" 2>&1 <<'EOF' &
import socket, subprocess, sys, time
pa, pb, prefix, va, vb = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
names = {f"{prefix}-{va}", f"{prefix}-{vb}"}
seen = {"both_running": None, pa: None, pb: None}
end = time.time() + 600
while time.time() < end and not all(seen.values()):
    running = set(subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split())
    if names <= running and not seen["both_running"]:
        seen["both_running"] = time.strftime("%H:%M:%S")
    for port in (pa, pb):
        if seen[port] or not names <= running:
            continue
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
                s.settimeout(5)
                data = s.recv(64)
                if data:
                    seen[port] = f"{time.strftime('%H:%M:%S')} {len(data)} bytes, first {data[:3].hex()}"
        except OSError:
            pass
    time.sleep(2)
for k, v in seen.items():
    print(f"{k}: {v}")
sys.exit(0 if all(seen.values()) else 1)
EOF
pp=$!
wait "$pa" || true; wait "$pb" || true
wait "$pp"; prc=$?
check "2a smoke on $A" 0 "$(cat "$OUT/t2-smoke-a.rc")"
check "2b smoke on $B" 0 "$(cat "$OUT/t2-smoke-b.rc")"
check "2c both running together, both TN3270 ports answered" 0 "$prc"
cat "$OUT/t2-probe.txt" >> "$OUT/summary.txt"

# --- 3. forced kill and restore on A ---------------------------------------------
step "3: IPL $A, create marker, kill -9 Hercules"
export DASD_VOLUME=$A OSE_LEASE_TOKEN=$TOK_A
creds_line=$(creds) || die "no credentials in $A"
u=${creds_line%% *}; p=${creds_line#* }
MNAME=$(guest_container ose-marker)
GUEST_EV=/work/evidence/ose-009/runs/$RUN
tools_image                            # pinned tools image (TOOLS_IMAGE), verified
docker rm -f "$MNAME" >/dev/null 2>&1 || true
MSYS_NO_PATHCONV=1 docker run -d --name "$MNAME" --user 1000:1000 $(guest_labels) -e GUEST_USER="$u" -e GUEST_PASS="$p" \
    -v "$(hostpath "$ROOT"):/ose:ro" -v "$A:/work" -w /work/sysgen/MVSCE "$TOOLS_IMAGE" \
    sh -c '[ ! -e "$0" ] && mkdir -p "$0" && exec python3 -I /ose/tests/integration/harness/marker.py --mode create-hold --evidence "$0" --hold 900' \
    "$GUEST_EV/create-hold" >/dev/null || die "cannot start the marker guest"
i=0
until MSYS_NO_PATHCONV=1 docker exec "$MNAME" test -f "$GUEST_EV/create-hold/marker-created" 2>/dev/null; do
    i=$((i + 1)); [ $i -lt 200 ] || break
    docker ps -q --filter "name=$MNAME" --filter status=running | grep -q . || break
    sleep 3
done
if MSYS_NO_PATHCONV=1 docker exec "$MNAME" test -f "$GUEST_EV/create-hold/marker-created" 2>/dev/null; then
    result "3a marker created while the guest ran: ok"
    # with --externalgui the Hercules process is named 'dyngui' (observed); match its command line
    hpid=$(MSYS_NO_PATHCONV=1 docker exec "$MNAME" sh -c 'pgrep -f "^hercules "' || true)
    [ -n "$hpid" ] || die "no Hercules process found in $MNAME"
    MSYS_NO_PATHCONV=1 docker exec "$MNAME" kill -9 "$hpid"
    result "3b kill -9 sent to hercules pid $hpid"
else
    result "3a marker created: FAIL (no marker-created file)"; fails=$((fails + 1))
fi
mrc=$(docker wait "$MNAME")
docker logs "$MNAME" > "$OUT/t3-create-hold-console.txt" 2>&1 || true
docker rm "$MNAME" >/dev/null 2>&1 || true
sed -i "s/$p/<redacted>/g" "$OUT/t3-create-hold-console.txt"
check "3c driver saw Hercules die (not a clean run)" 2 "$mrc"
grep -q "hercules exited by itself (rc -9)" "$OUT/t3-create-hold-console.txt" \
    && result "3d hercules ended by SIGKILL (rc -9): ok" || { result "3d SIGKILL not confirmed in console: FAIL"; fails=$((fails + 1)); }
mkdir -p "$OUT/create-hold"
export_evidence create-hold || { result "3 evidence export (verified): FAIL"; fails=$((fails + 1)); }

step "3: the modification survived the kill (check present, before restore)"
set +e; guest_run ose-marker /ose/tests/integration/harness/marker.py check-present --mode check --expect present > "$OUT/t3-check-present.txt" 2>&1; r=$?; set -e
check "3e marker present after kill -9, before restore" 0 "$r"

step "3: restore $SNAP into $A"
before_restore=$(volume_manifest "$A")
set +e; GPY restore --volume "$A" --name "$SNAP" --token "$TOK_A" > "$OUT/t3-restore.txt" 2>&1; r=$?; set -e
check "3f restore" 0 "$r"
after_restore=$(volume_manifest "$A")
[ "$before_restore" != "$after_restore" ] && result "3g volume content changed by restore: ok" \
    || { result "3g volume unchanged by restore: FAIL"; fails=$((fails + 1)); }

step "3: smoke on the restored $A"
set +e; sh "$ROOT/scripts/smoke.sh" all > "$OUT/t3-smoke-after-restore.txt" 2>&1; r=$?; set -e
check "3h JES2/TSO smoke after restore" 0 "$r"
set +e; guest_run ose-marker /ose/tests/integration/harness/marker.py check-absent --mode check --expect absent > "$OUT/t3-check-absent.txt" 2>&1; r=$?; set -e
check "3i marker gone after restore" 0 "$r"

# --- 4. a corrupted snapshot is refused and the volume is untouched --------------
step "4: corrupted copy of $SNAP"
BAD="$SNAP-corrupt"
SNAPROOT="${OSE_SNAPSHOT_DIR:-$ROOT/artifacts/guest/snapshots}"
rm -rf "$SNAPROOT/$BAD"; cp -R "$SNAPROOT/$SNAP" "$SNAPROOT/$BAD"
"$PY" -I -c 'import sys; p=sys.argv[1]; b=bytearray(open(p,"rb").read()); b[len(b)//2] ^= 1; open(p,"wb").write(bytes(b))' \
    "$SNAPROOT/$BAD/guest.tar"
set +e; GPY snapshot verify --name "$BAD" > "$OUT/t4-verify.txt" 2>&1; r=$?; set -e
check "4a verify refuses the corrupted snapshot" 6 "$r"
before=$(volume_manifest "$A")
set +e; GPY restore --volume "$A" --name "$BAD" --token "$TOK_A" > "$OUT/t4-restore.txt" 2>&1; r=$?; set -e
check "4b restore refuses the corrupted snapshot" 6 "$r"
after=$(volume_manifest "$A")
[ "$before" = "$after" ] && result "4c $A unchanged by the refused restore: ok ($after)" \
    || { result "4c $A changed by a refused restore: FAIL"; fails=$((fails + 1)); }
rm -rf "$SNAPROOT/$BAD"

step "done: $fails failure(s); evidence $OUT"
[ "$fails" -eq 0 ]

#!/bin/bash
# OSE-003: the in-container half of scripts/sysgen.sh. Implements
# upstream/sysgen/MANIFEST.md steps 1-3b inside the Hercules image, as uid 1000,
# with the repository at /ose (read for patches, pins.py and the lock) and the
# leased DASD volume at /work. Evidence goes to /work/evidence.
#
# Environment: SYSGEN_COMMIT RAKF_COMMIT MVP_COMMIT (pins), ATTEMPTS (sysgen
# retries with --CONTINUE, default 3), TIMEOUT (per-step seconds, default 3600),
# MVP_PIN_OVERRIDE (test 7 negative run only: a wrong MVP commit written into
# mvslovers.conf after validation), CONTINUE_FLAG (default --CONTINUE; set it
# empty for a --step restart), SYSGEN_STEP (sysgen --step value, for that restart).
set -euo pipefail
ATTEMPTS=${ATTEMPTS:-3}
TIMEOUT=${TIMEOUT:-3600}
LOCK=/ose/dependencies.lock.json
PINS="python3 -I /ose/scripts/lib/pins.py --lock $LOCK"
P01=${P01:-/ose/upstream/sysgen/patches/0001-pin-mvp-and-rakf-commits.patch}
S=${SYSGEN_DIR:-/work/sysgen}
E=${EVIDENCE_DIR:-/work/evidence}
mkdir -p "$E"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$E/wrapper.log"; }
(cd / && git config --global --add safe.directory '*')

if [ ! -d "$S/.git" ]; then
    log "step 1: sysgen $SYSGEN_COMMIT, LF-safe, patch P-01"
    git -c core.autocrlf=false clone -q --no-checkout /ose/artifacts/cache/src/sysgen "$S"
    git -C "$S" config core.autocrlf false
    git -C "$S" checkout -q "$SYSGEN_COMMIT"
    git -C "$S" apply --check "$P01"
    git -C "$S" apply "$P01"
    git -C "$S" diff --stat | tee -a "$E/wrapper.log"

    log "step 2: pre-stage RAKF and MVP at their pins"
    rm -rf "$S/temp/RAKF" "$S/MVSCE/MVP"; mkdir -p "$S/temp" "$S/MVSCE"
    git -c core.autocrlf=false clone -q --no-checkout https://github.com/mvslovers/RAKF "$S/temp/RAKF"
    git -C "$S/temp/RAKF" config core.autocrlf false
    git -C "$S/temp/RAKF" checkout -q --detach "$RAKF_COMMIT"
    git -c core.autocrlf=false clone -q --no-checkout https://github.com/MVS-sysgen/MVP "$S/MVSCE/MVP"
    git -C "$S/MVSCE/MVP" config core.autocrlf false
    git -C "$S/MVSCE/MVP" checkout -q --detach "$MVP_COMMIT"
else
    log "steps 1-2: existing tree in the volume, resuming it only if step 1b admits it"
fi

# step 1b (R03-1), on every invocation, fresh or resumed: the tree that is about
# to run must be exactly SYSGEN_COMMIT plus the reviewed patch P-01. HEAD must
# equal the pin, and the tracked working files (staged into a scratch index,
# objects in a scratch store) must hash to the same tree as the pin with P-01
# applied. Untracked build products (temp/, MVSCE/, logs) are not part of the
# comparison; the RAKF and MVP clones among them are checked by step 3.
verify_sysgen_tree() {
    local head cur exp scratch
    head=$(git -C "$S" rev-parse HEAD 2>/dev/null || echo none)
    [ "$head" = "$SYSGEN_COMMIT" ] || { log "step 1b FAILED: sysgen HEAD $head is not the pin $SYSGEN_COMMIT"; return 1; }
    scratch=$(mktemp -d)
    mkdir -p "$scratch/obj"
    (
        export GIT_OPTIONAL_LOCKS=0 GIT_OBJECT_DIRECTORY="$scratch/obj" \
               GIT_ALTERNATE_OBJECT_DIRECTORIES="$S/.git/objects"
        cd "$S"
        GIT_INDEX_FILE="$scratch/cur" git read-tree HEAD
        GIT_INDEX_FILE="$scratch/cur" git add -u
        GIT_INDEX_FILE="$scratch/cur" git write-tree > "$scratch/cur.tree"
        GIT_INDEX_FILE="$scratch/exp" git read-tree "$SYSGEN_COMMIT"
        GIT_INDEX_FILE="$scratch/exp" git apply --cached "$P01"
        GIT_INDEX_FILE="$scratch/exp" git write-tree > "$scratch/exp.tree"
    ) || { log "step 1b FAILED: could not compute the tree comparison"; rm -rf "$scratch"; return 1; }
    cur=$(cat "$scratch/cur.tree"); exp=$(cat "$scratch/exp.tree")
    if [ "$cur" != "$exp" ]; then
        log "step 1b FAILED: tracked files are not $SYSGEN_COMMIT + P-01 (tree $cur, expected $exp); differing paths:"
        GIT_OBJECT_DIRECTORY="$scratch/obj" GIT_ALTERNATE_OBJECT_DIRECTORIES="$S/.git/objects" \
            git -C "$S" diff --stat "$exp" "$cur" | tee -a "$E/wrapper.log"
        rm -rf "$scratch"; return 1
    fi
    rm -rf "$scratch"
    log "step 1b ok: HEAD $head, tracked tree $cur = pin + P-01"
}
verify_sysgen_tree || exit 10

log "step 3: validate before sysgen starts"
{ $PINS check-clone rakf "$S/temp/RAKF" && $PINS check-clone mvp "$S/MVSCE/MVP" \
  && $PINS check-mvp-packages "$S/MVSCE/MVP"; } > "$E/pins-pre.txt" 2>&1 \
  || { cat "$E/pins-pre.txt"; log "step 3 FAILED: sysgen not started"; exit 10; }
cat "$E/pins-pre.txt" | tee -a "$E/wrapper.log"

if [ -n "${MVP_PIN_OVERRIDE:-}" ]; then
    log "test 7 negative run: mvslovers.conf [mvp] commit -> $MVP_PIN_OVERRIDE"
    sed -i "s/^commit = $MVP_COMMIT$/commit = $MVP_PIN_OVERRIDE/" "$S/mvslovers.conf"
    grep -n "^commit = " "$S/mvslovers.conf" | tee -a "$E/wrapper.log"
fi

log "step 3a: sysgen --keep-temp --keep-backup --timeout $TIMEOUT (up to $ATTEMPTS attempts)"
cd "$S"
rc=1
for i in $(seq 1 "$ATTEMPTS"); do
    log "attempt $i start"
    set +e
    ./sysgen.py --keep-temp --keep-backup --timeout "$TIMEOUT" --version ose-003 ${CONTINUE_FLAG---CONTINUE} ${SYSGEN_STEP:+--step "$SYSGEN_STEP"} \
        > "$E/sysgen-attempt-$i.out" 2>&1
    rc=$?
    set -e
    log "attempt $i rc=$rc ($(cat .step 2>/dev/null || echo 'no .step'))"
    cp -f sysgen.log "$E/sysgen-attempt-$i.log" 2>/dev/null || true
    [ $rc -eq 0 ] && break
done
[ $rc -eq 0 ] || { log "step 3a FAILED after $ATTEMPTS attempts"; exit 20; }

log "step 3b: post-run pin evidence"
{ $PINS check-clone rakf "$S/temp/RAKF" && $PINS check-clone mvp "$S/MVSCE/MVP" \
  && $PINS check-mvp-packages "$S/MVSCE/MVP"; } > "$E/pins-post.txt" 2>&1 \
  || { cat "$E/pins-post.txt"; log "step 3b FAILED: build invalid"; exit 30; }
cat "$E/pins-post.txt" | tee -a "$E/wrapper.log"
grep -nE "pins commit|git clone target .* exists, checking out" "$S/sysgen.log" > "$E/sysgen-pin-lines.txt" || true
log "done"

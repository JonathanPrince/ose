#!/bin/sh
# OSE-003 acceptance test 1: build-host doctor. Usage: scripts/doctor.sh
# RC 0 when every check passes; RC 1 and one "FAIL ..." line per failed check.
# DOCTOR_USER=0 runs the in-container checks as root, to demonstrate a failure.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/lib/common.sh"
MIN_FREE_GB=${MIN_FREE_GB:-30}
fails=0
ok()   { echo "ok    $*"; }
fail() { echo "FAIL  $*"; fails=$((fails + 1)); }

# --- host side ---------------------------------------------------------------
if docker info >/dev/null 2>&1; then ok "docker engine running ($(docker version --format '{{.Server.Version}}' 2>/dev/null))"
else fail "docker engine not reachable (ADR-0003 option A needs Docker)"; fi

free_kb=$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')
if [ "${free_kb:-0}" -ge $((MIN_FREE_GB * 1024 * 1024)) ]; then ok "free disk $((free_kb / 1024 / 1024)) GB >= $MIN_FREE_GB GB"
else fail "free disk $((${free_kb:-0} / 1024 / 1024)) GB < $MIN_FREE_GB GB"; fi

# pins in scripts/lib/common.sh must equal the lock
PY=${PYTHON:-$(command -v python3 2>/dev/null || command -v python)}
if "$PY" -I - "$ROOT/dependencies.lock.json" "$HERCULES_COMMIT" "$SYSGEN_COMMIT" "$RAKF_COMMIT" "$MVP_COMMIT" <<'EOF'
import json, sys
lock = {c["name"]: c["commit"] for c in json.load(open(sys.argv[1], encoding="utf-8"))["components"]}
want = dict(zip(["hercules", "sysgen", "rakf", "mvp"], sys.argv[2:]))
bad = [f"{k}: script {v[:12]} lock {lock.get(k, '?')[:12]}" for k, v in want.items() if lock.get(k) != v]
bad and print("; ".join(bad)); sys.exit(1 if bad else 0)
EOF
then ok "script pins match dependencies.lock.json (hercules, sysgen, rakf, mvp)"
else fail "script pins differ from dependencies.lock.json (above)"; fi

if "$PY" -I "$ROOT/scripts/lib/debpins.py" check; then ok "Debian package pins valid (upstream/debian/packages.lock.json)"
else fail "upstream/debian/packages.lock.json invalid (above)"; fi

if docker image inspect "$HERC_IMAGE" >/dev/null 2>&1; then
    ok "image $HERC_IMAGE present"
    if MSYS_NO_PATHCONV=1 docker run --rm "$HERC_IMAGE" sh -c "$("$PY" -I "$ROOT/scripts/lib/debpins.py" verify-line hercules)"
    then ok "image carries the pinned Debian packages (regina-rexx, libregina3, libregina3-dev)"
    else fail "image packages differ from upstream/debian/packages.lock.json: rebuild with scripts/host/hercules-image.sh"; fi
else fail "image $HERC_IMAGE missing: run scripts/host/hercules-image.sh"; fi

# --- inside the build container ----------------------------------------------
if docker image inspect "$HERC_IMAGE" >/dev/null 2>&1; then
    out=$(MSYS_NO_PATHCONV=1 docker run --rm --user "${DOCTOR_USER:-1000}:${DOCTOR_USER:-1000}" \
        -e WANT_VER="$HERCULES_VERSION" -e WANT_COMMIT="$HERCULES_COMMIT" "$HERC_IMAGE" bash -c '
        f() { echo "FAIL  $*"; }; o() { echo "ok    $*"; }
        . /etc/os-release
        case "$ID" in debian|ubuntu) o "OS $PRETTY_NAME";; *) f "OS $ID is not Debian/Ubuntu (sysgen README)";; esac
        if [ "$(id -u)" -eq 0 ]; then f "running as root (sysgen README: never run as root)"; else o "not root (uid $(id -u))"; fi
        v=$(hercules --version 2>&1 | head -1)
        case "$v" in *"$WANT_VER"*) o "hercules: $v";; *) f "hercules version \"$v\" is not $WANT_VER";; esac
        case "$(hercules --version 2>&1)" in *"${WANT_COMMIT%"${WANT_COMMIT#???????}"}"*) o "hercules built from ${WANT_COMMIT%"${WANT_COMMIT#????????}"}";;
             *) f "hercules --version does not name commit ${WANT_COMMIT%"${WANT_COMMIT#???????}"}";; esac
        for t in hetinit dasdinit dasdload dasdls; do command -v $t >/dev/null && o "$t present" || f "$t missing"; done
        python3 -c "import sys; sys.exit(sys.version_info < (3, 9))" && o "python3 $(python3 -V 2>&1 | cut -d" " -f2)" || f "python3 >= 3.9 missing"
        command -v git >/dev/null && o "git $(git --version | cut -d" " -f3)" || f "git missing"
        for p in 3270 3505 3506 8888; do
            if (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null; then f "port $p already in use in the container"; else o "port $p free"; fi
        done
        echo "doctor-container-checks-complete"' 2>&1)
    run_rc=$?
    echo "$out" | grep -v '^doctor-container-checks-complete$'
    n=$(printf '%s\n' "$out" | grep -c '^FAIL')
    fails=$((fails + n))
    # R03-2: a container that failed to start, or died part-way, prints no FAIL
    # lines. Require both RC 0 and the completion sentinel.
    if [ "$run_rc" -ne 0 ]; then fail "in-container checks: docker run exited $run_rc"
    elif ! printf '%s\n' "$out" | grep -qx 'doctor-container-checks-complete'; then
        fail "in-container checks did not complete (no completion line)"; fi
fi

[ "$fails" -eq 0 ] && { echo "doctor: all checks passed"; exit 0; }
echo "doctor: $fails check(s) failed" >&2; exit 1

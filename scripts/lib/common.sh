# Shared helpers for the OSE-003 host scripts (sourced, not executed).
# Pins come from dependencies.lock.json; the values below are checked against
# it by scripts/doctor.sh, so a lock change that is not mirrored here fails.

ROOT=${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
CACHE="$ROOT/artifacts/cache/src"
EVID="$ROOT/artifacts/evidence/ose-003"

IMAGE_BASE="debian@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e"  # ADR-0003, as OSE-004
HERCULES_COMMIT=ee86c4de066fcdb2ec898a157ff4c687c5f01ce2   # SDL Hercules Release_4.9.1
HERCULES_VERSION=4.9.1
SYSGEN_COMMIT=4746195d33d9810bb9dfb0e8a3064a33efbb0559
RAKF_COMMIT=941b07dc19adb7a1a153caaeba96b659ff2ad3e0
MVP_COMMIT=4c004a599f6a49442fade63cdb3cc3a9e0fdf58a
HERC_IMAGE="ose-hercules:${HERCULES_VERSION}-${HERCULES_COMMIT%"${HERCULES_COMMIT#????????}"}"
DASD_VOLUME=${DASD_VOLUME:-ose-sysgen-1}   # the leased DASD set (docs/status.md)

die() { echo "${0##*/}: $*" >&2; exit 1; }
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

# fetch NAME URL COMMIT: LF-safe clone at an exact commit under $CACHE.
fetch() {
    d="$CACHE/$1"
    if [ ! -d "$d/.git" ]; then
        git -c core.autocrlf=false clone -q "$2" "$d" || die "clone $1 failed"
        git -C "$d" config core.autocrlf false
    fi
    git -C "$d" -c core.autocrlf=false checkout -q "$3" 2>/dev/null \
        || { git -C "$d" fetch -q origin && git -C "$d" -c core.autocrlf=false checkout -q "$3"; } \
        || die "checkout $1@$3 failed"
    [ "$(git -C "$d" rev-parse HEAD)" = "$3" ] || die "$1 is not at pinned $3"
    [ -z "$(git -C "$d" status --porcelain)" ] || die "$1 working tree is not clean"
}

# Docker on Windows (Git Bash) needs Windows paths and no MSYS path rewriting.
hostpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else echo "$1"; fi; }

# hrun [docker-args...] -- SCRIPT: run SCRIPT as uid 1000 in the Hercules image,
# with the repository at /ose and the leased DASD volume at /work.
hrun() {
    args=""
    while [ $# -gt 1 ] && [ "$1" != "--" ]; do args="$args $1"; shift; done
    [ "$1" = "--" ] && shift
    # shellcheck disable=SC2086
    MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 $args \
        -v "$(hostpath "$ROOT"):/ose" -v "$DASD_VOLUME:/work" -w /work \
        "$HERC_IMAGE" bash -euo pipefail -c "$1"
}

# --- pinned tools image and guest credentials (OSE-003; shared by smoke.sh and
# deploy.sh since OSE-004, moved here unchanged) ---------------------------
PY=${PYTHON:-$(command -v python3 2>/dev/null || command -v python)}
DEBPINS="$PY -I $ROOT/scripts/lib/debpins.py"
# R03-5 / ADR-0006: the tools layer adds s3270 and netbase, pinned by
# version and .deb SHA-256 in upstream/debian/packages.lock.json. The tag names
# the pin set, and the installed versions are re-checked on every use, so an
# older or hand-built image with the same name is never trusted.
TOOLS_IMAGE=   # set by tools_image(), so sourcing this file needs no Python

tools_image() {
    TOOLS_IMAGE="${HERC_IMAGE}-tools-$($DEBPINS digest tools)" || die "debpins: lock invalid"
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

# --- OSE-009 guest leases and isolation ---------------------------------------
# Every guest-mutating script holds the lease on $DASD_VOLUME for its whole run
# (scripts/guest/guest.py; leases are host-wide in OSE_LEASE_DIR). If the caller
# already holds it, it passes OSE_LEASE_TOKEN and the script only checks it.
GUEST_PY="$ROOT/scripts/guest/guest.py"
holder_pid() { # the Windows PID under Git Bash (MSYS PIDs are not Windows PIDs)
    if [ -r "/proc/$$/winpid" ]; then cat "/proc/$$/winpid"; else echo "$$"; fi
}
guest_lease_begin() {
    if [ -n "${OSE_LEASE_TOKEN:-}" ]; then
        "$PY" -I "$GUEST_PY" lease check --volume "$DASD_VOLUME" --token "$OSE_LEASE_TOKEN" >/dev/null \
            || die "OSE_LEASE_TOKEN does not hold the lease on $DASD_VOLUME (see above)"
        return 0
    fi
    OSE_LEASE_TOKEN=$("$PY" -I "$GUEST_PY" lease acquire --volume "$DASD_VOLUME" \
        --task "${OSE_TASK:-${0##*/}}" --holder-pid "$(holder_pid)") || die "cannot lease $DASD_VOLUME (see above)"
    export OSE_LEASE_TOKEN
    GUEST_LEASE_OWNED=1
    trap guest_lease_end EXIT
}
guest_lease_end() {
    if [ "${GUEST_LEASE_OWNED:-}" = 1 ]; then
        "$PY" -I "$GUEST_PY" lease release --volume "$DASD_VOLUME" --token "$OSE_LEASE_TOKEN" >/dev/null \
            || echo "${0##*/}: could not release the lease on $DASD_VOLUME" >&2
        GUEST_LEASE_OWNED=
    fi
}
# container name for this volume, so guests on different volumes never collide
guest_container() { echo "$1-$DASD_VOLUME"; }
# optional TN3270 for a person: GUEST_TN3270_PORT=13270 publishes 3270 on 127.0.0.1 only
guest_ports() {
    if [ -n "${GUEST_TN3270_PORT:-}" ]; then
        case "$GUEST_TN3270_PORT" in *[!0-9]*) die "GUEST_TN3270_PORT must be a number";; esac
        echo "-p 127.0.0.1:$GUEST_TN3270_PORT:3270"
    fi
}

# --- guest job runner with verified evidence export (OSE-004 R04-3; shared
# by deploy.sh and audit-listing.sh since OSE-011) ---------------------------
# sha256 and relative path of every file under a directory, sorted (host and container)
MANIFEST='import hashlib,os,sys
r=sys.argv[1]; out=[]
for d,_,fs in os.walk(r):
    for f in fs:
        p=os.path.join(d,f); rel=os.path.relpath(p,r).replace(os.sep,"/")
        if rel!="console.txt": out.append(hashlib.sha256(open(p,"rb").read()).hexdigest()+"  "+rel)
sys.stdout.buffer.write(("\n".join(sorted(out)) + "\n").encode())'   # LF on every OS (print gives CRLF on Windows)

# guest_run NAME SCRIPT MODE [args]: run SCRIPT (python, in the pinned tools
# image) as container NAME on $DASD_VOLUME with --evidence $GUEST_EV/MODE and
# the MVSCE02 credentials in GUEST_USER/GUEST_PASS; then collect its console
# (redacted) and export the evidence verified to $OUT/MODE. Callers set OUT
# (a new host directory) and GUEST_EV (a new guest directory). From OSE-004
# deploy.sh, generalised unchanged in behaviour for OSE-011.
guest_run() {
    NAME=$(guest_container "$1"); script=$2; mode=$3; shift 3
    tools_image
    creds_line=$(creds) || die "cannot read guest credentials from $DASD_VOLUME"
    u=${creds_line%% *}; p=${creds_line#* }
    [ -n "$u" ] && [ -n "$p" ] && [ "$u" != "$p" ] || die "no MVSCE02 entry in users.conf"
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    # shellcheck disable=SC2046
    MSYS_NO_PATHCONV=1 docker run -d --name "$NAME" --user 1000:1000 $(guest_ports) \
        -e GUEST_USER="$u" -e GUEST_PASS="$p" \
        -v "$(hostpath "$ROOT"):/ose:ro" -v "$DASD_VOLUME:/work" -w /work/sysgen/MVSCE "$TOOLS_IMAGE" \
        sh -c '[ ! -e "$0" ] && mkdir -p "$0" && s=$1 && shift && exec python3 -I "$s" --evidence "$0" "$@"' \
        "$GUEST_EV/$mode" "$script" "$@" >/dev/null
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

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

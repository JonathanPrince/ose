#!/bin/sh
# OSE-003: build the build-host image (ADR-0003 option A) with SDL Hercules
# compiled from the pinned source. Usage: scripts/host/hercules-image.sh
#
# Hercules 4.9.1 ships prebuilt x86_64 static libraries for its external
# packages (crypto, decNumber, SoftFloat, telnet) in the source tree, and
# configure uses them by default. hercules-helper (pinned v0.9.9) would clone
# those packages from their default branches, unpinned; so this script builds
# Hercules directly and uses the helper only as the reference for the Debian
# package list (hercules-helper package-requirements.txt, hyperion-buildall.sh
# l.2149-2156). Regina REXX comes from Debian (regina-rexx, libregina3-dev):
# the Hercules test suite (make check) is written in REXX and refuses to run
# without it, as the helper's own default build also installs Regina.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
. "$ROOT/scripts/lib/common.sh"

fetch hyperion https://github.com/SDL-Hercules-390/hyperion.git "$HERCULES_COMMIT"
mkdir -p "$EVID"
# ADR-0006: all apt packages from one Debian snapshot; Regina pinned
# by version and .deb SHA-256 (upstream/debian/packages.lock.json).
PY=${PYTHON:-$(command -v python3 2>/dev/null || command -v python)}
APT_RUN=$("$PY" -I "$ROOT/scripts/lib/debpins.py" install-line hercules) || die "debpins: lock invalid"

log "building $HERC_IMAGE from $CACHE/hyperion"
MSYS_NO_PATHCONV=1 docker build --progress=plain -t "$HERC_IMAGE" \
    -f - "$(hostpath "$CACHE/hyperion")" > "$EVID/hercules-image-build.log" 2>&1 <<EOF || die "image build failed (log: artifacts/evidence/ose-003/hercules-image-build.log)"
FROM $IMAGE_BASE
RUN $APT_RUN
RUN useradd -u 1000 -m ose
COPY --chown=ose:ose . /src/hyperion
USER ose
RUN git config --global --add safe.directory /src/hyperion \\
 && mkdir /src/hyperion/build && cd /src/hyperion/build \\
 && ../configure --prefix=/opt/hercules --enable-custom="OSE-003 build of $HERCULES_COMMIT" \\
 && make -j"\$(nproc)" && make check
USER root
RUN cd /src/hyperion/build && make install && rm -rf /src/hyperion \\
 && echo /opt/hercules/lib > /etc/ld.so.conf.d/hercules.conf && ldconfig
ENV PATH=/opt/hercules/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
USER ose
WORKDIR /work
EOF

MSYS_NO_PATHCONV=1 docker run --rm "$HERC_IMAGE" sh -c 'hercules --version 2>&1 | head -3; \
    dpkg-query -W -f="\${Package}=\${Version}\n" gcc make python3 git cmake libbz2-dev zlib1g-dev regina-rexx libregina3 libregina3-dev; \
    grep -h "^deb " /etc/apt/sources.list' \
    > "$EVID/hercules-version.txt" 2>&1 || die "image smoke test failed"
cat "$EVID/hercules-version.txt"

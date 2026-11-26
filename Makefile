# OSE stable command surface (spec section 4). Targets exit nonzero on failure.
# Implemented: check, test-host, build (OSE-004), doctor, fetch, sysgen, smoke (OSE-003).
# The rest name their owning task.
PYTHON ?= python3

.PHONY: check test-host doctor fetch build sysgen smoke deploy test-guest test-security package restore

check:
	$(PYTHON) scripts/check_repo.py

test-host:
	$(PYTHON) -m unittest discover -s tests/host -v

define notyet
	@echo "make $@: not implemented yet (owner: $(1)); see docs/status.md" >&2; exit 2
endef

doctor:
	sh scripts/doctor.sh

# pinned sources and the Hercules build-host image (ADR-0003 option A)
fetch:
	sh scripts/host/hercules-image.sh

build:
	sh scripts/build.sh all
sysgen:
	sh scripts/sysgen.sh run

# two cold IPLs, JES2 and TSO smoke (OSE-003 tests 3-5)
smoke:
	sh scripts/smoke.sh all

deploy:        ; $(call notyet,OSE-004)
test-guest:    ; $(call notyet,OSE-006/OSE-009)
test-security: ; $(call notyet,OSE-007 (plan only in M0))
package:       ; $(call notyet,M5)
restore:       ; $(call notyet,OSE-009)

# OSE stable command surface (spec section 4). Targets exit nonzero on failure.
# M0: only `check` and `test-host` are implemented; others name their owning task.
PYTHON ?= python3

.PHONY: check test-host doctor fetch build sysgen deploy test-guest test-security package restore

check:
	$(PYTHON) scripts/check_repo.py

test-host:
	$(PYTHON) -m unittest discover -s tests/host -v

define notyet
	@echo "make $@: not implemented yet (owner: $(1)); see docs/status.md" >&2; exit 2
endef

doctor:        ; $(call notyet,OSE-003)
fetch:         ; $(call notyet,OSE-002/OSE-003)
build:         ; $(call notyet,OSE-004)
sysgen:        ; $(call notyet,OSE-003)
deploy:        ; $(call notyet,OSE-004)
test-guest:    ; $(call notyet,OSE-006/OSE-009)
test-security: ; $(call notyet,OSE-007 (plan only in M0))
package:       ; $(call notyet,M5)
restore:       ; $(call notyet,OSE-009)

# OSE — Open Systems Environment for MVS/CE

OSE is a proposed native UNIX-style subsystem for MVS 3.8j under Hercules. It will be distributed as an optional MVS/CE Sysgen profile.

**Status: M0 (baseline and source audit). Nothing is implemented.** Treat every architecture statement as a proposal until milestone evidence supports it. Current state, blockers and next tasks: [docs/status.md](docs/status.md).

## Start here

| You are | Read |
|---|---|
| Any agent or contributor | [AGENTS.md](AGENTS.md), then [spec/OSE-SPEC.md](spec/OSE-SPEC.md), [docs/status.md](docs/status.md), [tasks/README.md](tasks/README.md) |
| Picking up a task | your card in [tasks/](tasks/), plus the ADRs and interfaces it names |
| Reviewing evidence | [docs/research/](docs/research/) and [dependencies.lock.json](dependencies.lock.json) |
| Making a decision | [docs/adr/](docs/adr/) |

Model-specific wrapper files (for example `CLAUDE.md`) only point to `AGENTS.md`. They must not add rules.

## Layout

See spec section 4. In short: `spec/` holds the normative spec, `docs/` the ADRs, research, interfaces, runbooks and status, `tasks/` the task cards and usage log, `upstream/` manifests and patches (never vendored copies), and `src/`, `include/ose/`, `jcl/` and `tests/` code (empty until M1). `artifacts/` is git-ignored and holds logs, dumps and DASD images.

## Commands

The stable command surface comes from spec section 4. During M0 only `make check` works. The other targets exit with status 2 and name the task that owns them.

```
make check          # repository consistency checks (python3 scripts/check_repo.py)
make doctor         # OSE-003
make fetch          # OSE-002 / OSE-003
make build          # OSE-004
make sysgen         # OSE-003
make deploy         # OSE-004
make test-host      # host unit tests (tests/host)
make test-guest     # OSE-006 / OSE-009
make test-security  # OSE-007 (plan only in M0)
make package        # M5
make restore        # OSE-009
```

The intended build host is non-root Debian/Ubuntu (see ADR-0003). `make check` also runs anywhere that has Python 3.9 or newer: `python3 scripts/check_repo.py`.

## Licensing

Not yet decided. OSE-002 investigates the rights of every upstream component. Until those rights are resolved, do not redistribute generated images or upstream material.

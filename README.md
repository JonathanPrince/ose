# OSE — Open Systems Environment for MVS/CE

OSE is a proposed native UNIX-style subsystem for MVS 3.8j under Hercules. It will be distributed as an optional MVS/CE Sysgen profile.

**Current priority: M0a, a reusable MVP package development platform.** The pinned build/guest/HELLO baseline is accepted. Finish generic isolation/recovery (OSE-009), then package configuration, MVP examples and export acceptance (OSE-014), before new OSE-specific audits (M0b) or subsystem work. Current state, blockers and next tasks: [docs/status.md](docs/status.md).

## Start here

| You are | Read |
|---|---|
| Any agent or contributor | [AGENTS.md](AGENTS.md), then [spec/OSE-SPEC.md](spec/OSE-SPEC.md), [docs/status.md](docs/status.md), [tasks/README.md](tasks/README.md) |
| Picking up a task | your card in [tasks/](tasks/), plus the ADRs and interfaces it names |
| Reviewing evidence | [docs/research/](docs/research/) and [dependencies.lock.json](dependencies.lock.json) |
| Making a decision | [docs/adr/](docs/adr/) |

Model-specific wrapper files (for example `CLAUDE.md`) only point to `AGENTS.md`. They must not add rules.

## Layout

See spec section 4. In short: `spec/` holds the normative spec, `docs/` the ADRs, research, interfaces, runbooks and status, `tasks/` the task cards and usage log, `upstream/` manifests and patches (never vendored copies), and `src/`, `include/ose/`, `jcl/` and `tests/` hold code and verification fixtures. `artifacts/` is git-ignored and holds logs, dumps and DASD images.

## Commands

The stable command surface comes from spec section 4. Build, deploy and host/guest smoke commands exist for the accepted baseline. Generic MVP packaging and recovery are the next M0a deliverables; unsupported targets still exit nonzero and name their owner.

```
make check          # repository consistency checks (python3 scripts/check_repo.py)
make doctor         # OSE-003
make fetch          # OSE-002 / OSE-003
make build          # OSE-004
make sysgen         # OSE-003
make deploy         # OSE-004
make test-host      # host unit tests (tests/host)
make test-guest     # generic platform tests: OSE-014; OSE-specific tests after M0a
make test-security  # OSE-007 (plan in M0b)
make package        # generic MVP workflow: OSE-014/M0a; OSE distribution: M5
make restore        # OSE-009
```

The intended build host is non-root Debian/Ubuntu (see ADR-0003). `make check` also runs anywhere that has Python 3.9 or newer: `python3 scripts/check_repo.py`.

## Licensing

Not yet decided. OSE-002 investigates the rights of every upstream component. Until those rights are resolved, do not redistribute generated images or upstream material.

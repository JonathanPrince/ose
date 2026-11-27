# Architecture decision records

- Files are named `NNNN-short-title.md` and numbered sequentially. A number is never reused.
- Status is one of `Proposed`, `Accepted`, `Rejected`, `Superseded by NNNN` or `Deprecated`. Only the human maintainer sets `Accepted`.
- Once an ADR is Accepted it is immutable. To change it, write a new ADR that supersedes it.
- Per spec §8, approved ADRs outrank the specification. A Proposed ADR has no authority over the spec.
- Every new interface or dependency decision needs an ADR (spec §7).
- Each ADR cites its evidence (research notes, test IDs) and labels its confidence as `observed`, `documented` or `hypothesis`.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-repository-as-shared-memory.md) | Repository as shared memory; task protocol | Proposed |
| [0002](0002-evidence-and-provenance.md) | Evidence, provenance and confidence labels | Proposed |
| [0003](0003-m0-build-host.md) | M0 build host on a Windows workstation | Proposed (open options) |
| [0004](0004-dependency-pinning.md) | Dependency pinning and upstream patch policy | Proposed |
| [0005](0005-pins-for-components-sysgen-does-not-pin.md) | Pins for components Sysgen does not pin (toolchain, Hercules, MVP) | Proposed |
| [0006](0006-hercules-direct-build-and-debian-package-pins.md) | Build Hercules directly at its pinned commit; pin build-host Debian packages (supersedes part of 0005 §2) | Accepted |

Architecture ADRs (execution model, service ABI, identity) are **deliberately not written yet**. OSE-010 produces them from M0 evidence.

## Template

```
# NNNN — Title
Status: Proposed
Date:
Deciders:
Supersedes / superseded by:

## Context (with evidence links and confidence)
## Decision
## Alternatives considered
## Consequences (incl. what would make us revisit)
```

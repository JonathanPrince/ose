# Platform-first work queue

Human direction, 2026-11-27: finish the reusable MVP package development platform before starting new OSE-specific work. Spec §§1.1, 4.1 and 5 define the order; this replaces the previous post-M0 OSE-014 ordering.

## Current execution order

| Stage | Task | Prerequisites | Acceptance |
|---|---|---|---|
| M0a, next | OSE-009: generic guest lease, isolation, snapshot/recovery | OSE-003 merged | exclusive leases, configurable ports, independent guest copies, forced-failure restore and corruption rejection |
| M0a | OSE-014: generic package configuration, shared harness, MVP workflow, two examples and export gate | OSE-009 accepted; accepted inventory/pins/toolchain/build baseline | all spec §5.1 checks; independent clean-checkout repeat; standalone export; independent review and human M0a acceptance |
| M0b, after M0a | OSE-006: UFSD guest tests | OSE-014 gate; OSE-003/004/005 | existing two-client, persistence, binary and failure tests |
| M0b, after M0a | OSE-007: identity/security feasibility audit | OSE-014 gate; OSE-002/005 | existing trusted-caller evidence and negative test plan |
| M0b, after M0a | OSE-008: execution model/runtime audit | OSE-014 gate; OSE-002/004 | target-supported mechanisms and experiment designs |
| M0b gate | OSE-010: OSE baseline review and M1 queue | M0a plus all existing M0 audit dependencies | all remaining OSE M0 evidence/decisions; human gate approval |
| M1 onward | OSE subsystem implementation | M0a and M0b | existing milestone gates, including non-waivable M3 multi-user security |

```text
accepted inventory / pins / build / deploy / toolchain
                    |
                 OSE-009
                    |
                 OSE-014 -- independent review + human M0a acceptance
                    |
          +---------+---------+
          |         |         |
       OSE-006   OSE-007   OSE-008
          +---------+---------+
                    |
                 OSE-010 -- human M0b acceptance
                    |
                 OSE M1+
```

OSE-014 does not depend on OSE-010. Its validated local export may pass the technical gate while external publication awaits a human destination/license/release decision. Existing accepted work is reused, not redone solely to rename it. During M0a, new work must serve generic package development or fix the foundation's safety/reliability. Remaining OSE-specific audits stay BACKLOG, including source-only work. Guest mutations remain serialized under the current lease contract until OSE-009 replaces it through review.

## Existing baseline and retained task identities

| Task | Scope | Role |
|---|---|---|
| OSE-001 | Repository/docs/task protocol | existing governance |
| OSE-002 | Upstream inventory/licenses/pins | reusable baseline |
| OSE-003 | Host doctor, Sysgen, native JES/TSO smoke | reusable baseline |
| OSE-004 | Toolchain and HELLO build/deploy/runtime proof | reusable baseline/example |
| OSE-005 | UFSD source/interface audit | accepted OSE evidence; consumed in M0b |
| OSE-011 | Terminal/name audit and guest listing | accepted OSE evidence; no repeat required solely for scheduling |
| OSE-012 | C subset/libc inventory and probes | reusable toolchain evidence |
| OSE-013 | MVP/RAKF pin enforcement | reusable baseline |

No previous security/UFSD/process requirement is waived by the split. See each card for exact acceptance and docs/status.md for current evidence/state.

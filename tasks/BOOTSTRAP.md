# Initial ready queue

| Task | Scope | Depends | Tier | Acceptance |
|---|---|---|---|---|
| OSE-001 | Initialize repository, docs, task schema, CI skeleton | none | economy | clean checkout; AGENTS.md and status accessible; no vendor requirement |
| OSE-002 | Inventory upstream versions/licenses and pin dependencies | 001 | economy + standard review | manifest with source evidence and unresolved rights |
| OSE-003 | Build host doctor and Sysgen wrapper | 002 | standard | clean non-root build, boot evidence, native TSO/JES smoke |
| OSE-004 | CC/370 + MBT hello compile/deploy harness | 002 | standard | actual guest execution, RC and output captured |
| OSE-005 | UFSD source/interface audit | 002 | standard | service/ABI and permission gaps documented with source locations |
| OSE-006 | UFSD cross-space filesystem tests | 003,004,005 | standard | two clients, persistence, byte roundtrip, failure cases |
| OSE-007 | RAKF and SSI identity feasibility audit | 002,005 | high | trusted caller hypotheses, evidence, negative test plan |
| OSE-008 | Address-space/TCB and runtime audit | 002,004 | high | candidate mechanisms and runnable experiment designs |
| OSE-009 | Guest lease, snapshot and recovery harness | 003 | standard | isolated images, serialized mutation, recovery proof |
| OSE-010 | M0 gate review and M1 task decomposition | 001–009 | high + human | all M0 evidence reviewed; ADRs and scoped M1 queue |

Economy tasks may run concurrently on disjoint files. Tasks 003, 004, 006 and 009 must coordinate guest ownership. No M1 implementation until M0 review.

## Coordinator additions (OSE-001 and the OSE-002 rework, 2026-11-26; approved by the human 2026-11-26)

| Task | Scope | Depends | Tier | Why added |
|---|---|---|---|---|
| OSE-011 | TSO terminal API and name-collision audit | 002 (003 for guest listing) | economy → standard | spec §10 "terminal APIs"; §3.5 "name subject to collision audit" |
| OSE-012 | Target C subset and LIBC/370 POSIX inventory | 002 (004 harness for probes) | economy + standard review | spec §10 "target C subset"; §2 "audit existing POSIX functions" |

| OSE-013 | Enforce MVP and RAKF pins (sysgen patch P-01 plus wrapper check) | 002 | standard | OSE-002 review finding 3: a mutable MVP fetch must be enforced, not just recorded. OSE-003 now depends on it |

Clarifications that do not change the dependencies above:
- OSE-004 compiles on the host after 002, but its guest run needs the image from OSE-003.
- OSE-010 also depends on 011 and 012.
- OSE-011's guest listing job also holds a lease.

Each task's full card is `tasks/OSE-NNN-*.md`.

## Dependency graph and parallelism

```
001 ──> 002 ─┬─> 013 ─> 003 ─┬─> 009
             │                ├─> 004(guest) ─┬─> 006 <── 005
             ├─> 004(host) ───────────────────┤
             ├─> 005 ──> 007                  └─> 008
             ├─> 011(source) ... 011(guest needs 003)
             └─> 012(inventory) ... 012(probes need 004)
all ──> 010 (gate)
```

**Wave 1 (after 002):** 013, 004-host, 005, 011-source and 012-inventory can run in parallel on disjoint files. 003 follows 013. 005 and 012 are pure source reading and suit economy or standard tiers.
**Wave 2 (needs the guest; serialize on the lease):** 004-guest, 009, 011-guest, then 006.
**Wave 3 (high tier, no guest needed):** 007 after 005; 008 after 004.

The critical path is 002 → 013 → 003 → 004-guest → 006 → 010. ADR-0003 is accepted (option A). The earliest open decisions are approving OSE-013 and choosing the OSE-002 gate option (docs/status.md).

## Reusable development environment follow-up (human direction, 2026-11-27)

OSE-014 tracks the separate repository export after the M0 gate (OSE-010). It prepares a reusable foundation for other MVP package projects, with an actual MVP install test, second independent example and export/license review (spec §5.1). It does not change the existing M0 dependency graph or authorize publication. Reuse boundaries should guide harness work during M0.

# Interface contracts

These are versioned contracts (ABI, encoding, process, security). An Accepted interface contract has the same authority as an ADR (spec §8). The ABI is versioned independently of OSE releases (spec §9).

| Contract | Version | Status |
|---|---|---|
| (none yet) | | |

Observed upstream interfaces:

| Document | Upstream pin | Task |
|---|---|---|
| [ufsd-observed.md](ufsd-observed.md) | ufsd v1.5.2 `1a63bf52` | OSE-005 (unreviewed) |

Two kinds of document live here:
- `*-observed.md`: what an **existing** upstream interface (such as UFSD) does at a pinned commit. These are evidence, not OSE contracts. OSE-005 produces the first one.
- `ose-*.md`: OSE-owned contracts, drafted only after OSE-010.

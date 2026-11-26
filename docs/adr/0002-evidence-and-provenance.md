# 0002 — Evidence, provenance and confidence labels
Status: Accepted
Date: 2026-11-26
Deciders: human maintainer (pending)

## Context
Spec §8 requires provenance and confidence for every claim, and requires historical MVS 3.8j behavior to be kept separate from modern z/OS behavior. Much of the public material describes z/OS, and LLMs tend to mix the two up.

## Decision
Every factual claim in `docs/research/`, `docs/interfaces/` or an ADR carries:

| Field | Content |
|---|---|
| Source | URL, plus commit SHA or document number/edition |
| Location | file:line, macro name, section or page |
| Excerpt | short quotation or paraphrase (no bulk copying of IBM or unlicensed text) |
| Verified | ISO date and who verified it (task ID, tier) |
| Confidence | `observed` (we ran or read it at a pinned commit), `documented` (stated by a primary source but not exercised), `hypothesis` (inference, untested) |
| Platform | `MVS 3.8j`, `MVS/CE build <commit>`, `Hercules <ver>`, or `z/OS (not applicable as evidence)` |

Research notes are named `docs/research/YYYY-MM-DD-<topic>.md`, are append-only, and may contain corrections. Failed experiments and ABEND diagnostics (completion code, PSW, module, offset) are recorded too, not only successes.

A claim based only on modern z/OS documentation can never be `observed` or `documented` for OSE.

## Consequences
Research notes take longer to write, but a reviewer can re-check any claim. A security or ABI conclusion needs `observed` or `documented` evidence before it can reach an Accepted ADR.

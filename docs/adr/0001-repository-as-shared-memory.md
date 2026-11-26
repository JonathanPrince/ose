# 0001 — Repository as shared memory; task protocol
Status: Accepted
Date: 2026-11-26
Deciders: human maintainer (pending); proposed by bootstrap coordinator (OSE-001)

## Context
Spec §7–8 require the work to be resumable by any model or human without chat history, vendor memory or embeddings. Several agents of different tiers will work in parallel, and some will be local models.

## Decision
1. The Git repository is the only project memory. Every decision, piece of evidence, status change and handoff is committed as UTF-8 Markdown, JSON or JSONL.
2. Each task has a card `tasks/OSE-NNN-<slug>.md` made from `tasks/TEMPLATE.md`. The lifecycle, tiers, escalation, guest-resource rule and usage log are defined in `tasks/README.md`.
3. Each task works on its own branch `task/<ID>-<slug>` in a separate worktree where possible. One integration owner updates `docs/status.md` and resolves conflicts. The human merges.
4. `docs/status.md` is the single index of milestone state, the guest lease and open questions.
5. `tasks/usage.jsonl` records cost and quality data. Unknown values are `null`.
6. `scripts/check_repo.py` (`make check`) enforces the structure: required files, card fields, valid statuses, ADR headers and parseable JSON/JSONL. It runs locally with no vendor dependency. The CI workflow only wraps it.

## Alternatives considered
- An external tracker (GitHub Issues, Jira): rejected as the source of truth because it is not available offline and not in the repo. It may mirror the cards later.
- A custom orchestrator: deferred, per spec §10. Run the protocol by hand until coordination overhead has been measured.

## Consequences
- Agents spend some tokens reading the cards, and context packs keep that small.
- `docs/status.md` is a merge hotspot, so only the integration owner edits it.
- Revisit once usage data shows that coordination overhead dominates.

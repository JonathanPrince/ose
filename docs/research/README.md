# Research notes

Evidence, source references and experiments. ADR-0002 sets the format: name files `YYYY-MM-DD-<topic>.md`, append rather than rewrite, and give every claim a source, location, verification date and confidence (`observed` / `documented` / `hypothesis`) plus its platform.

Do not commit bulk copies of IBM manuals or upstream source. Cite a document number or a commit with a line reference and quote only the short excerpts needed.

| Note | Task | Topic |
|---|---|---|
| [2026-11-26-upstream-recon.md](2026-11-26-upstream-recon.md) | OSE-001 | Upstream heads, RAKF redirect, Sysgen defaults, build host |
| [2026-11-26-sysgen-pins.md](2026-11-26-sysgen-pins.md) | OSE-002 | What Sysgen fetches, pin mechanics, asset hash verification, leads |
| [2026-11-26-licensing.md](2026-11-26-licensing.md) | OSE-002 | License evidence per component; redistribution questions |
| [2026-11-26-toolchain.md](2026-11-26-toolchain.md) | OSE-004 | cc370 build in the pinned container, hello compile, C dialect probes, maclib370 blocker, mbt deploy transport |

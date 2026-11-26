# Source and encoding conventions

This is the separate encoding document that spec §7 calls for. Status: Proposed with ADR-0001. Revisit after OSE-004 shows how CC/370 and MBT expect their sources.

- **Repository text**: UTF-8, LF line endings, no BOM (enforced by `.gitattributes`).
- **Host tools**: POSIX shell (`#!/bin/sh` or bash, stated explicitly) and Python 3.9+ standard library only, unless an ADR adds a dependency.
- **Guest sources** (JCL, assembler, C for CC/370): stored in ASCII/UTF-8 on the host and converted to EBCDIC during deploy. Code page TBD (OSE-004; candidate IBM-037/IBM-1047, **unverified**). JCL and assembler lines stay within 80 columns, with the columns 72–80 rules respected. Any non-ASCII character in a guest source is an error until a conversion table is pinned.
- **Fixtures** that must keep exact bytes (binary round-trip tests) are marked `binary` in `.gitattributes`.
- **Naming**: MVS member and data set names in uppercase, at most 8 characters per qualifier. OSE high-level qualifier TBD (avoid collisions; OSE-011 checks).
- **Evidence and logs**: `artifacts/<task-id>/<UTC timestamp>/`, never committed. Commit only a summary with sha256 checksums.

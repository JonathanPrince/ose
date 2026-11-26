#!/usr/bin/env python3
"""OSE repository consistency checks (ADR-0001). Standard library only.

Usage: python3 scripts/check_repo.py [REPO_ROOT]
Exit status: 0 if all checks pass, 1 if any check fails.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "spec/OSE-SPEC.md",
    "docs/status.md",
    "docs/compatibility.md",
    "docs/conventions.md",
    "docs/adr/README.md",
    "tasks/README.md",
    "tasks/TEMPLATE.md",
    "tasks/BOOTSTRAP.md",
    "dependencies.lock.json",
]
TASK_STATUSES = {"BACKLOG", "READY", "CLAIMED", "IMPLEMENTED", "REVIEW",
                 "VERIFIED", "MERGED", "BLOCKED"}
TASK_FIELDS = ["Status", "Milestone", "Dependencies", "Owner", "Risk",
               "Model tier", "Budget", "Baseline commit"]
TASK_SECTIONS = ["## Goal", "## Acceptance tests", "## Escalation triggers",
                 "## Handoff", "## Independent review"]
ADR_STATUSES = {"Proposed", "Accepted", "Rejected", "Superseded", "Deprecated"}
LOCK_KEYS = ["name", "source_url", "commit", "version", "license_spdx",
             "redistribution", "pinned_by", "verified_date", "verified_by"]
USAGE_KEYS = ["task", "attempt", "date", "role", "tier"]
LINK_FILES = ["README.md", "AGENTS.md", "docs/status.md", "tasks/BOOTSTRAP.md",
              "docs/adr/README.md", "docs/research/README.md"]
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def _field(text: str, name: str) -> str | None:
    m = re.search(rf"^{re.escape(name)}:[ \t]*(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def check_required(root: Path) -> list[str]:
    return [f"missing required file: {p}" for p in REQUIRED_FILES
            if not (root / p).is_file()]


def check_tasks(root: Path) -> list[str]:
    errs: list[str] = []
    for card in sorted((root / "tasks").glob("OSE-*.md")):
        text = card.read_text(encoding="utf-8")
        m = re.match(r"OSE-(\d{3})-[a-z0-9-]+\.md$", card.name)
        if not m:
            errs.append(f"{card.name}: name must be OSE-NNN-lower-slug.md")
            continue
        first = text.splitlines()[0] if text else ""
        if not first.startswith(f"# OSE-{m.group(1)} "):
            errs.append(f"{card.name}: first line must start with '# OSE-{m.group(1)} '")
        for f in TASK_FIELDS:
            if _field(text, f) is None:
                errs.append(f"{card.name}: missing header field '{f}:'")
        status = _field(text, "Status")
        if status is not None:
            word = status.split()[0] if status.split() else ""
            if word not in TASK_STATUSES:
                errs.append(f"{card.name}: invalid Status '{word}'")
        for s in TASK_SECTIONS:
            if s not in text:
                errs.append(f"{card.name}: missing section '{s}'")
    return errs


def check_adrs(root: Path) -> list[str]:
    errs: list[str] = []
    seen: set[str] = set()
    for adr in sorted((root / "docs" / "adr").glob("*.md")):
        if adr.name == "README.md":
            continue
        m = re.match(r"(\d{4})-[a-z0-9-]+\.md$", adr.name)
        if not m:
            errs.append(f"adr {adr.name}: name must be NNNN-lower-slug.md")
            continue
        if m.group(1) in seen:
            errs.append(f"adr {adr.name}: duplicate number {m.group(1)}")
        seen.add(m.group(1))
        text = adr.read_text(encoding="utf-8")
        status = _field(text, "Status")
        if status is None or not status.split() or status.split()[0] not in ADR_STATUSES:
            errs.append(f"adr {adr.name}: missing or invalid 'Status:'")
    return errs


def check_lock(root: Path) -> list[str]:
    path = root / "dependencies.lock.json"
    if not path.is_file():
        return []  # reported by check_required
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"dependencies.lock.json: invalid JSON: {e}"]
    errs: list[str] = []
    if data.get("schema_version") != 1:
        errs.append("dependencies.lock.json: schema_version must be 1")
    comps = data.get("components")
    if not isinstance(comps, list):
        return errs + ["dependencies.lock.json: 'components' must be a list"]
    names: set[str] = set()
    for i, c in enumerate(comps):
        label = f"dependencies.lock.json component[{i}]"
        if not isinstance(c, dict):
            errs.append(f"{label}: must be an object")
            continue
        label = f"dependencies.lock.json {c.get('name', f'[{i}]')}"
        for k in LOCK_KEYS:
            if k not in c:
                errs.append(f"{label}: missing key '{k}'")
        if c.get("name") in names:
            errs.append(f"{label}: duplicate name")
        names.add(c.get("name"))
        if "commit" in c and not SHA1.match(str(c["commit"])):
            errs.append(f"{label}: commit must be a full 40-hex SHA")
        if "verified_date" in c and not DATE.match(str(c["verified_date"])):
            errs.append(f"{label}: verified_date must be YYYY-MM-DD")
        for a in c.get("artifacts", []) or []:
            if not SHA256.match(str(a.get("sha256", ""))):
                errs.append(f"{label}: artifact {a.get('url')} needs 64-hex sha256")
    return errs


def check_usage(root: Path) -> list[str]:
    path = root / "tasks" / "usage.jsonl"
    if not path.is_file():
        return []
    errs: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            errs.append(f"usage.jsonl:{n}: invalid JSON: {e}")
            continue
        if not isinstance(obj, dict):
            errs.append(f"usage.jsonl:{n}: must be an object")
            continue
        for k in USAGE_KEYS:
            if k not in obj:
                errs.append(f"usage.jsonl:{n}: missing key '{k}'")
    return errs


def check_links(root: Path) -> list[str]:
    errs: list[str] = []
    for rel in LINK_FILES:
        f = root / rel
        if not f.is_file():
            continue
        for target in LINK.findall(f.read_text(encoding="utf-8")):
            if re.match(r"^[a-z]+:", target):
                continue  # external URL; not checked offline
            if not (f.parent / target).exists():
                errs.append(f"{rel}: broken relative link '{target}'")
    return errs


CHECKS = [check_required, check_tasks, check_adrs, check_lock, check_usage, check_links]


def run(root: Path) -> list[str]:
    errs: list[str] = []
    for chk in CHECKS:
        errs.extend(chk(root))
    return errs


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    errs = run(root)
    for e in errs:
        print(f"FAIL {e}")
    print(f"check_repo: {len(errs)} problem(s)" if errs else "check_repo: OK")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

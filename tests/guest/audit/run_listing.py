"""OSE-011 acceptance 2: run jcl/audit/list-libraries.jcl on the guest, parse its
step RCs and every LISTDS member list, and build the name-collision table.

Runs inside the pinned tools image in the MVSCE/ directory of the leased volume
(started by scripts/audit-listing.sh). Reuses the OSE-003 drivers (Herc,
IPL_SEQUENCE, step_rcs, shutdown_check) and the OSE-004 deck helpers unchanged.
The job card gets USER=/PASSWORD= at submit time from GUEST_USER/GUEST_PASS
(never stored); the password is redacted from every saved file.

Exit 0 only if the job ran with the expected RCs (CFG* 0000, LIST <= 0012), the
spool was parsed, and the shutdown was clean. A name collision is a finding,
not a failure: it is reported in the result.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

LIB = Path("/ose/scripts/lib")
JCL = Path("/ose/jcl/audit/list-libraries.jcl")
HELLO_GUEST = Path("/ose/tests/guest/hello/hello_guest.py")   # OSE-004 deck and spool helpers
CANDIDATES = {"command": ["OMVS", "OSH"], "hlq": ["OSE"], "stc": ["OSE", "OSED"], "subsystem": ["OSE1", "OSES"]}
CFG_STEPS = ["CFGLNK", "CFGAPF", "CFGSSN", "CFGJES", "CFGTSO", "CFGLOG"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def add_credentials(jcl: str, user: str, pw: str) -> str:
    """Insert USER=/PASSWORD= into the job card's continuation line."""
    old = "//             MSGLEVEL=(1,1)\n"
    if jcl.count(old) != 1:
        raise ValueError("job card continuation not found")
    return jcl.replace(old, f"//             MSGLEVEL=(1,1),USER={user},PASSWORD={pw}\n")


def qualify_user_libraries(jcl: str, user: str) -> str:
    """Unquoted LISTDS names stand for the submitter's libraries (&SYSUID in
    TSOLOGON). Batch TSO does not prefix them (observed 2026-11-27: 'DATA SET
    CLIST NOT IN CATALOG'), so qualify them with the user ID at submit time."""
    return re.sub(r"^ LISTDS ([A-Z][A-Z0-9@#$]{0,7}) MEMBERS$", rf" LISTDS '{user}.\1' MEMBERS", jcl, flags=re.M)


def listds_commands(jcl: str) -> list:
    """LISTDS targets as written: 'FULLY.QUALIFIED' or an unquoted name that
    TSO prefixes with the submitter's user ID (e.g. CLIST)."""
    return re.findall(r"^ LISTDS '?([^' ]+)'? MEMBERS", jcl, re.M)


def ssn_table(text: str) -> dict:
    """Decode the HMBLIST LISTLOAD text of IEFJSSNT (subsystem names table):
    its bytes in cp037, the 4-character names before the X'FFFFFFFF' end
    marker, and the printable strings (eye-catchers) for the record."""
    lines = text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if "LISTING OF LOAD MODULE IEFJSSNT" in l)
    except StopIteration:
        return {"found": False}
    data = bytearray()
    for l in lines[start:]:
        if "END OF LOAD MODULE LISTING" in l:
            break
        m = re.match(r"\s+([0-9A-F]{6})\s{4}((?:[0-9A-F]{2,8}\s*)+)$", l)
        if m:
            data += bytes.fromhex("".join(m.group(2).split()))
    end = data.find(b"\xff\xff\xff\xff")
    table = data[:end] if end >= 0 else data
    names = sorted({table[i:i + 4].decode("cp037") for i in range(0, len(table) - 3, 4)
                    if table[i:i + 4] != b"\x40" * 4 and table[i:i + 4].decode("cp037").isalnum()})
    strings = re.findall(r"[A-Z0-9*/ ]{6,}", data.decode("cp037", errors="replace"))
    return {"found": True, "bytes": len(data), "end_marker_offset": end, "names_before_end": names,
            "strings": [s.strip() for s in strings if s.strip()]}


NAME = r"[A-Z@#${][A-Z0-9@#${]{0,7}"     # '{' is EBCDIC X'C0' as printed (e.g. IGC0013{)


def parse_members(lines: list) -> list:
    """LISTDS MEMBERS lines -> member names and alias names. An entry is
    '  NAME' or '  NAME  ALIAS(A,B,...)'; a long alias list continues on the
    next lines and ends with ')'. Unparsed lines come back as '?<text>'."""
    names, in_alias = [], False
    for b in lines:
        t = b.strip()
        if not t:
            continue
        if in_alias:
            part, in_alias = (t[:-1], False) if t.endswith(")") else (t, True)
            names += [a for a in part.split(",") if a]
            continue
        m = re.fullmatch(rf"({NAME})(?:\s+ALIAS\((.*))?", t)
        if not m:
            names.append("?" + t)
            continue
        names.append(m.group(1))
        if m.group(2) is not None:
            rest = m.group(2)
            part, in_alias = (rest[:-1], False) if rest.endswith(")") else (rest, True)
            names += [a for a in part.split(",") if a]
    return names


def listds_sections(text: str, dsns: list) -> dict:
    """For each DSN: ('members', [names]) | ('error', [message lines]) | ('missing', [])."""
    lines = [l.rstrip() for l in text.split("\n")]
    out = {}
    for dsn in dsns:
        idx = [i for i, l in enumerate(lines) if re.fullmatch(rf"\s*LISTDS '?{re.escape(dsn)}'? MEMBERS\s*", l)]
        if not idx:
            out[dsn] = ("missing", [])
            continue
        i = idx[-1] + 1
        block = []
        while i < len(lines) and not re.match(r"\s*(LISTDS|LISTCAT) ", lines[i]) and lines[i].strip() != "END":
            block.append(lines[i])
            i += 1
        if "--MEMBERS--" in [b.strip() for b in block]:
            j = [b.strip() for b in block].index("--MEMBERS--") + 1
            out[dsn] = ("members", parse_members(block[j:]))
        else:
            out[dsn] = ("error", [b.strip() for b in block if b.strip()][:6])
    return out


def catalog_result(text: str, hlq="OSE") -> dict:
    """Outcome of the job's two LISTCAT commands for the HLQ: 'not found',
    'found' or None (no output, so no evidence either way)."""
    out = {}
    for key, cmd in (("level", rf"LISTCAT LEVEL\({hlq}\) ALL"), ("entries", rf"LISTCAT ENTRIES\('{hlq}'\) ALL")):
        m = re.search(rf"^\s*{cmd}\s*$(.*?)(?=^\s*(?:LISTCAT|LISTDS) |^\s*END\s*$|\Z)", text, re.M | re.S)
        if not m:
            out[key] = None
        elif re.search(rf"IDC3012I ENTRY {hlq}\.? NOT FOUND", m.group(1)):
            out[key] = "not found"
        elif re.search(r"NONVSAM|ALIAS|CLUSTER|USERCATALOG", m.group(1)):
            out[key] = "found"
        else:
            out[key] = None
    return out


def evidence_problems(sections: dict, ssn: dict, catalog: dict) -> list:
    """Why the audit evidence is incomplete (review R11-G1); empty when complete.
    A collision verdict is only as good as the listing behind it."""
    problems = []
    for dsn, (kind, detail) in sections.items():
        if kind == "missing":
            problems.append(f"{dsn}: no LISTDS output")
        elif kind == "error" and not any("NOT IN CATALOG" in d for d in detail):
            problems.append(f"{dsn}: LISTDS failed: {detail[:2]}")   # e.g. access denied: not searched
        elif kind == "members":
            bad = [n for n in detail if n.startswith("?")]
            if bad:
                problems.append(f"{dsn}: {len(bad)} unparsed member line(s), first {bad[0]!r}")
    if not ssn.get("found"):
        problems.append("IEFJSSNT: no HMBLIST listing in the spool")
    elif ssn.get("bytes", 0) == 0 or ssn.get("end_marker_offset", -1) < 0:
        problems.append(f"IEFJSSNT: listing incomplete (bytes {ssn.get('bytes')}, "
                        f"end marker {ssn.get('end_marker_offset')})")
    for key, v in catalog.items():
        if v is None:
            problems.append(f"catalog: no result for LISTCAT {key}")
    return problems


def analyse(text: str, dsns: list) -> dict:
    """Everything the audit concludes from the spool, including why its evidence
    would be incomplete. main() and the host replay tests both call this."""
    sections = listds_sections(text, dsns)
    members = {d: m for d, (k, m) in sections.items() if k == "members"}
    ssn = ssn_table(text)
    catalog = catalog_result(text)
    return {
        "libraries": {d: {"kind": k, "count": len(m) if k == "members" else None,
                          "detail": m if k != "members" else None} for d, (k, m) in sections.items()},
        "members": members,
        "collisions": collisions(sections),
        "unparsed_lines": {d: [n for n in m if n.startswith("?")] for d, m in members.items()
                           if any(n.startswith("?") for n in m)},
        "ssn_table": ssn,
        "catalog": catalog,
        "evidence_problems": evidence_problems(sections, ssn, catalog),
    }


def collisions(sections: dict) -> list:
    rows = []
    names = sorted({n for v in CANDIDATES.values() for n in v})
    for name in names:
        hits = [dsn for dsn, (kind, mem) in sections.items() if kind == "members" and name in mem]
        rows.append({"name": name, "kinds": [k for k, v in CANDIDATES.items() if name in v], "found_in": hits})
    return rows


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--mvsce", type=Path, default=Path("/work/sysgen/MVSCE"))
    a.add_argument("--evidence", type=Path, required=True)
    args = a.parse_args()
    user, pw = os.environ["GUEST_USER"], os.environ["GUEST_PASS"]
    ev = args.evidence
    ev.mkdir(parents=True, exist_ok=True)
    smoke = load("mvs_smoke", LIB / "mvs-smoke.py")
    hg = load("hello_guest", HELLO_GUEST)
    template = qualify_user_libraries(JCL.read_text(encoding="ascii"), user)
    dsns = listds_commands(template)
    result = {"user": user, "jcl": str(JCL), "listds": dsns}
    ok = True
    t0 = time.time()
    h = smoke.Herc(args.mvsce, ev / "listing-hercules.log")
    try:
        for _mid, rx in smoke.IPL_SEQUENCE:
            h.wait(rx, smoke.IPL_TIMEOUT)
        result["ipl_seconds"] = round(time.time() - t0)
        print(f"IPL complete after {result['ipl_seconds']}s")
        h.send("/$S PRT1")
        h.wait(r"\$HASP(160|170|000).*PRINTER1|\$HASP150|PRINTER1", 60)
        deck = b"".join(hg.jcl_cards(add_credentials(template, user, pw)))
        hg.submit_ebcdic(deck)
        print(f"submitted OSELIST ({len(deck) // 80} cards)")
        result["ended"] = h.wait(r"\$HASP395\s+OSELIST\s+ENDED", hg.JOB_TIMEOUT)
        steps = CFG_STEPS + ["LIST"]
        rcs, text = [], ""
        for _ in range(90):
            text = hg.printer_text(args.mvsce)
            rcs = smoke.step_rcs(args.mvsce / "printers" / "prt00e.txt", "OSELIST")
            if len(rcs) >= len(steps) or hg.job_failures(text, "OSELIST"):
                break
            time.sleep(2)
        time.sleep(3)
        text = hg.printer_text(args.mvsce)
        got = dict(rcs)
        result["step_rcs"] = rcs
        result["failures"] = hg.job_failures(text, "OSELIST")
        # CFG* 0-4 (HMBLIST ends 4 with AMB126I); LIST 0-12 (LISTCAT of an absent
        # name ends 4, a library absent on the image up to 12): jcl header
        rc_ok = all(got.get(s) is not None and int(got[s]) <= 4 for s in CFG_STEPS) \
            and got.get("LIST") is not None and int(got["LIST"]) <= 12
        print(f"OSELIST step RCs {rcs} -> {'ok' if rc_ok else 'UNEXPECTED'}")
        ok &= rc_ok and not result["failures"]
        result.update(analyse(text, dsns))
        print(f"  IEFJSSNT: {result['ssn_table']}")
        for d, v in result["libraries"].items():
            print(f"  {d:24} {v['kind']:8} {v['count'] if v['kind'] == 'members' else v['detail']}")
        for r in result["collisions"]:
            print(f"  candidate {r['name']:5} {r['kinds']} found in {r['found_in'] or 'none'}")
        print(f"  catalog OSE: {result['catalog']}")
        for p in result["evidence_problems"]:
            print(f"  EVIDENCE INCOMPLETE: {p}")
        ok &= not result["evidence_problems"]
    except Exception as e:  # noqa: BLE001
        ok = False
        result["error"] = str(e)
        print(f"ERROR {e}", file=sys.stderr)
    finally:
        rc = h.stop()
        mark = h.stop_mark if h.stop_mark is not None else len(h.console)
        stopped, missing = smoke.shutdown_check(h.console, mark)
        result.update(hercules_rc=rc, quit_fallback=h.quit_fallback, exited_before_shutdown=h.exited_early,
                      shutdown_messages=stopped, shutdown_missing=missing, total_seconds=round(time.time() - t0))
        if h.quit_fallback or rc != 0 or h.exited_early or missing:
            ok = False
        red = lambda s: s.replace(pw, "<redacted>")  # noqa: E731
        (ev / "listing-mvslog.txt").write_text(red("\n".join(h.console)) + "\n", encoding="utf-8")
        (ev / "listing-prt00e.txt").write_text(red(hg.printer_text(args.mvsce)), encoding="utf-8")
        result["ok"] = bool(ok)
        (ev / "listing-result.json").write_text(red(json.dumps(result, indent=1)) + "\n", encoding="utf-8")
        print(f"listing: ok={ok} hercules rc={rc} shutdown_missing={missing} total {result['total_seconds']}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

"""OSE-004 guest acceptance 2-4: deploy HELLO, confirm it by a listing job,
run it in batch (step RC = PARM value, output parsed from spool) and from TSO.

Runs inside the pinned tools image (scripts/deploy.sh starts it), in the MVSCE/
directory of the leased DASD volume. It reuses the OSE-003 drivers unchanged:
Herc, IPL_SEQUENCE, step_rcs and shutdown_check from scripts/lib/mvs-smoke.py,
S3270 from scripts/lib/tso-smoke.py.

Transport: the XMIT's raw 80-byte EBCDIC records go in-stream behind
DD DATA,DLM= in a deck sent untranslated to the EBCDIC card reader 001A
(127.0.0.1:3506), then TSO RECEIVE unpacks it. That is upstream sysgen's own
method for the mvslovers products (sysgen.py submit_binary, mvslovers.py
stage_parts). No FTPD and no mvsMF are used (research 2026-11-26-toolchain T-6).

  hello_guest.py --mode deploy --xmit HELLO.xmit --evidence DIR   (acceptance 2)
  hello_guest.py --mode run --evidence DIR                         (acceptance 3, 4)

Credentials come from the environment (GUEST_USER, GUEST_PASS) and are
redacted from every saved file. Exit 0 only if every check passed and the
shutdown was clean (OSE-003 rules).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import socket
import sys
import time
from pathlib import Path

LIB = Path("/ose/scripts/lib")
JCL = Path("/ose/jcl/hello")
CODEPAGE = "cp037"
CARD = 80
DLM_CANDIDATES = ["@@", "$$", "##"] + [a + b for a in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for b in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
HELLO_LINE = re.compile(r"^\s*OSE-004 HELLO RC=(\d+)\s*$")
JOB_TIMEOUT = 600


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ decks
def fill(template: str, values: dict) -> str:
    for k, v in values.items():
        template = template.replace("{" + k + "}", v)
    left = re.findall(r"\{[A-Z]+\}", template)
    if left:
        raise ValueError(f"unfilled placeholders {left}")
    return template


def jcl_cards(text: str) -> list:
    cards = []
    for n, line in enumerate(text.rstrip("\n").split("\n"), 1):
        line = line.rstrip()
        if len(line) > CARD or (line.startswith("//") and not line.startswith("//*") and len(line) > 71):
            raise ValueError(f"JCL line {n} too long: {line!r}")
        cards.append(line.ljust(CARD).encode(CODEPAGE))
    return cards


def choose_dlm(records) -> str:
    starts = {bytes(r[:2]) for r in records}
    for c in DLM_CANDIDATES:
        if c.encode(CODEPAGE) not in starts:
            return c
    raise ValueError("no usable DLM")


TARGET_DELETE = "  DELETE {HLQ}.OSE.LOAD NONVSAM SCRATCH PURGE\n"


def deploy_deck(xmit: bytes, values: dict, omit_target_delete=False) -> bytes:
    """The deploy job with the XMIT in-stream. omit_target_delete drops DELOLD's
    DELETE of the target library: the negative test for the GONE guard (R04-2),
    which must then stop STAGE, RECV and CLEANUP."""
    if len(xmit) % CARD:
        raise ValueError(f"XMIT length {len(xmit)} is not a multiple of {CARD}")
    records = [xmit[i:i + CARD] for i in range(0, len(xmit), CARD)]
    tpl = (JCL / "deploy.jcl").read_text(encoding="ascii")
    if omit_target_delete:
        if tpl.count(TARGET_DELETE) != 1:
            raise ValueError("deploy.jcl: target DELETE line not found exactly once")
        tpl = tpl.replace(TARGET_DELETE, "")
        if tpl.count("//OSEHDEP  JOB") != 1:
            raise ValueError("deploy.jcl: job card not found")
        tpl = tpl.replace("//OSEHDEP  JOB", "//OSEHSTL  JOB")   # own name: its IEF142I lines stay apart
    head, tail = tpl.split("\n{XMIT}\n")
    vals = dict(values, DLM=choose_dlm(records))
    return b"".join(jcl_cards(fill(head, vals)) + records + jcl_cards(fill(tail, vals)))


def text_deck(name: str, values: dict) -> bytes:
    return b"".join(jcl_cards(fill((JCL / name).read_text(encoding="ascii"), values)))


def submit_ebcdic(data: bytes, port=3506):
    with socket.create_connection(("127.0.0.1", port), timeout=30) as s:
        s.sendall(data)


# ------------------------------------------------------------------ spool
def printer_text(mvsce: Path) -> str:
    p = mvsce / "printers" / "prt00e.txt"
    return p.read_text(encoding="latin-1").replace("\f", "\n") if p.exists() else ""


def job_failures(text: str, job: str) -> list:
    """JCL errors and ABENDs of the job, from its allocation messages."""
    rx = re.compile(rf"(IEF452I\s+{re.escape(job)}\b.*|IEF450I\s+{re.escape(job)}\b.*ABEND.*|"
                    rf"IEF453I\s+{re.escape(job)}\b.*)")
    return [m.group(0).strip() for m in rx.finditer(text)]


def run_job(mod, h, mvsce, job, deck, steps, result):
    """Submit, wait for $HASP395, then wait until every step's IEF142I is in the spool."""
    submit_ebcdic(deck)
    print(f"submitted {job} ({len(deck) // CARD} cards)")
    ended = h.wait(rf"\$HASP395\s+{re.escape(job)}\s+ENDED", JOB_TIMEOUT)
    rcs, text = [], ""
    for _ in range(90):                 # the printer writes after the job ends
        text = printer_text(mvsce)
        rcs = mod.step_rcs(mvsce / "printers" / "prt00e.txt", job)
        if len(rcs) >= len(steps) or job_failures(text, job):
            break
        time.sleep(2)
    got = dict(rcs)
    fails = job_failures(text, job)
    checks = {s: (got.get(s) == code) for s, code in steps.items()}
    result[job] = {"ended": ended, "step_rcs": rcs, "expected": steps, "failures": fails, "checks": checks}
    for s, code in steps.items():
        print(f"{job}: step {s} expected {code} got {got.get(s)} {'ok' if checks[s] else 'MISMATCH'}")
    for f in fails:
        print(f"{job}: {f}")
    return all(checks.values()) and not fails, text


def members_listed(text: str, dsn: str) -> list:
    """Member names under --MEMBERS-- following the LISTDS header line for dsn."""
    lines = [l.rstrip() for l in text.split("\n")]
    for i, l in enumerate(lines):
        if l.strip() == dsn:
            for j in range(i + 1, min(i + 12, len(lines))):
                if lines[j].strip() == "--MEMBERS--":
                    names = []
                    for k in range(j + 1, len(lines)):
                        m = re.fullmatch(r"\s+([A-Z@#$][A-Z0-9@#$]{0,7})", lines[k])
                        if not m:
                            break
                        names.append(m.group(1))
                    return names
    return []


# ------------------------------------------------------------------ TSO
def tso_call(tso, ev: Path, user, pw, dsn, parm, result):
    """Log on, CALL the program, look for its line on the screen, log off.
    Plain CALL first; if libc370's "*SYSPRINT" did not reach the terminal,
    ALLOC F(SYSPRINT) DA(*) and CALL again. Both outcomes are recorded."""
    t = tso.S3270(ev / "tso-s3270.log")
    n = 0
    seen = {"ready": False, "call_plain": False, "call_after_alloc": None, "logoff": False}

    def snap(label):
        nonlocal n
        scr = t.screen()
        n += 1
        (ev / f"tso-{n:02d}-{label}.txt").write_text(scr.replace(pw, "<redacted>") + "\n", encoding="utf-8")
        return scr

    def wait_for(pattern, label, timeout=60, poke=None, fail=True):
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(2)
            t.do("Wait(3,Output)")
            scr = t.screen()
            if re.search(pattern, scr, re.M):
                return snap(label)
            if poke and re.search(poke, scr, re.M):
                t.do("Enter()")
        snap(label + "-timeout")
        if fail:
            raise TimeoutError(f"{label}: no {pattern!r} within {timeout}s")
        return None

    def command(cmd):
        t.do("Clear()")
        t.do(f'String("{cmd}")')
        t.do("Enter()")

    want = rf"^\s*OSE-004 HELLO RC={parm}\s*$"
    try:
        ok = False
        end = time.time() + 300
        while time.time() < end and not ok:
            ok, _ = t.do("Connect(127.0.0.1:3270)")
            if not ok:
                time.sleep(5)
        if not ok:
            raise RuntimeError("cannot connect to 127.0.0.1:3270")
        t.do("Wait(60,InputField)")
        snap("connected")
        t.do("Enter()")
        wait_for(r"TSO Logon ===>", "vtam-logon", poke=r"CLEAR the screen or hit ENTER")
        t.do(f'String("LOGON {user}/{pw}")', secret=True)
        t.do("Enter()")
        wait_for(r"^\s*READY\s*$", "ready", timeout=120, poke=r"\*\*\*\s*$")
        seen["ready"] = True
        command(f"CALL '{dsn}(HELLO)' '{parm}'")
        seen["call_plain"] = wait_for(want, "call-plain", timeout=45, poke=r"\*\*\*\s*$", fail=False) is not None
        if not seen["call_plain"]:
            command("ALLOC F(SYSPRINT) DA(*)")
            wait_for(r"^\s*READY\s*$", "alloc", timeout=30, poke=r"\*\*\*\s*$", fail=False)
            command(f"CALL '{dsn}(HELLO)' '{parm}'")
            seen["call_after_alloc"] = wait_for(want, "call-after-alloc", timeout=45, poke=r"\*\*\*\s*$",
                                                fail=False) is not None
        command("LOGOFF")
        wait_for(r"IKJ56470I|TSO Logon ===>|CLEAR the screen or hit ENTER", "logoff", timeout=60)
        seen["logoff"] = True
    except Exception as e:  # noqa: BLE001
        print(f"tso: ERROR {e}", file=sys.stderr)
        seen["error"] = str(e)
    finally:
        t.close()
    result["tso"] = seen
    return seen["ready"] and (seen["call_plain"] or bool(seen["call_after_alloc"])) and seen["logoff"]


# ------------------------------------------------------------------ main
def main():
    a = argparse.ArgumentParser()
    a.add_argument("--mode", choices=("deploy", "deploy-stale", "run"), required=True)
    a.add_argument("--mvsce", type=Path, default=Path("/work/sysgen/MVSCE"))
    a.add_argument("--evidence", type=Path, required=True)
    a.add_argument("--xmit", type=Path)
    a.add_argument("--volume", default="PUB000", help="RECEIVE VOLUME()")
    a.add_argument("--tso-parm", default="7")
    args = a.parse_args()
    user, pw = os.environ["GUEST_USER"], os.environ["GUEST_PASS"]
    ev = args.evidence
    ev.mkdir(parents=True, exist_ok=True)
    smoke = load("mvs_smoke", LIB / "mvs-smoke.py")
    values = {"USER": user, "PASS": pw, "HLQ": user, "VOLUME": args.volume}
    dsn = f"{user}.OSE.LOAD"
    result = {"mode": args.mode, "dsn": dsn}
    ok = True
    if args.mode in ("deploy", "deploy-stale"):
        if not args.xmit:
            a.error(f"--mode {args.mode} needs --xmit")
        xmit = args.xmit.read_bytes()
        result["xmit_sha256"] = hashlib.sha256(xmit).hexdigest()
        print(f"xmit {args.xmit} sha256 {result['xmit_sha256']} ({len(xmit) // CARD} records)")
    t0 = time.time()
    h = smoke.Herc(args.mvsce, ev / f"{args.mode}-hercules.log")
    try:
        for mid, rx in smoke.IPL_SEQUENCE:
            h.wait(rx, smoke.IPL_TIMEOUT)
        result["ipl_seconds"] = round(time.time() - t0)
        print(f"IPL complete after {result['ipl_seconds']}s")
        h.send("/$S PRT1")
        h.wait(r"\$HASP(160|170|000).*PRINTER1|\$HASP150|PRINTER1", 60)
        if args.mode == "deploy":
            good, _ = run_job(smoke, h, args.mvsce, "OSEHDEP", deploy_deck(xmit, values),
                              {"DELOLD": "0000", "GONE": "0004", "STAGE": "0000", "RECV": "0000", "CLEANUP": "0000"}, result)
            ok &= good
            # acceptance 2: presence by a separate listing job, whatever the deploy RCs said
            good, text = run_job(smoke, h, args.mvsce, "OSEHLST", text_deck("list.jcl", values),
                                 {"LISTDS": "0000"}, result)
            members = members_listed(text, dsn)
            result["members"] = members
            print(f"OSEHLST: {dsn} members {members}")
            ok &= good and "HELLO" in members
        elif args.mode == "deploy-stale":
            # R04-2 negative test. First a normal deploy, so the target library
            # exists; then the same deploy without DELOLD's DELETE of it (the
            # failed-delete case). GONE must end 0000 and STAGE, RECV and
            # CLEANUP must not execute: no IEF142I for them and no RECEIVE.
            good, text = run_job(smoke, h, args.mvsce, "OSEHDEP", deploy_deck(xmit, values),
                                 {"DELOLD": "0000", "GONE": "0004", "STAGE": "0000", "RECV": "0000",
                                  "CLEANUP": "0000"}, result)
            ok &= good
            received_before = text.count("Receive into '")
            good, text = run_job(smoke, h, args.mvsce, "OSEHSTL",
                                 deploy_deck(xmit, values, omit_target_delete=True),
                                 {"DELOLD": "0000", "GONE": "0000"}, result)
            time.sleep(5)                       # let the printer finish the job
            text = printer_text(args.mvsce)
            ran = {s for s, _ in smoke.step_rcs(args.mvsce / "printers" / "prt00e.txt", "OSEHSTL")}
            not_run = [l.strip() for l in text.split("\n") if re.search(r"OSEHSTL\s+\w+.*NOT (RUN|EXECUTED)", l)]
            received_after = text.count("Receive into '")
            guard = {"executed_steps": sorted(ran), "not_run_messages": not_run,
                     "receives_before": received_before, "receives_after": received_after}
            result["stale_guard"] = guard
            print(f"OSEHSTL: {guard}")
            ok &= good and not (ran & {"STAGE", "RECV", "CLEANUP"}) and received_after == received_before
        else:
            good, text = run_job(smoke, h, args.mvsce, "OSEHRUN", text_deck("run.jcl", values),
                                 {"RC0": "0000", "RC4": "0004"}, result)
            lines = [m.group(0).strip() for m in map(HELLO_LINE.match, text.split("\n")) if m]
            result["hello_lines"] = lines
            want = ["OSE-004 HELLO RC=0", "OSE-004 HELLO RC=4"]
            print(f"OSEHRUN: output lines {lines} (want {want})")
            ok &= good and sorted(lines) == want
            tso = load("tso_smoke", LIB / "tso-smoke.py")
            good = tso_call(tso, ev, user, pw, dsn, args.tso_parm, result)
            print(f"TSO: {result['tso']}")
            ok &= good
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
        (ev / f"{args.mode}-mvslog.txt").write_text(red("\n".join(h.console)) + "\n", encoding="utf-8")
        (ev / f"{args.mode}-prt00e.txt").write_text(red(printer_text(args.mvsce)), encoding="utf-8")
        result["ok"] = bool(ok)
        (ev / f"{args.mode}-result.json").write_text(red(json.dumps(result, indent=1)) + "\n", encoding="utf-8")
        print(f"{args.mode}: ok={ok} hercules rc={rc} shutdown_missing={missing} total {result['total_seconds']}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

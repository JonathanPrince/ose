"""OSE-009 recovery test driver: a package-neutral guest modification.

Runs in the pinned tools image in the MVSCE/ directory of a leased volume.
  marker.py --mode create-hold --evidence DIR [--hold 900]
      IPL; job OSEMARK deletes, then creates and catalogs <user>.OSE009.MARKER
      and LISTCATs it (all steps 0000); writes DIR/marker-created; then waits to
      be killed (the test sends kill -9 to Hercules). If nobody kills it within
      --hold seconds it shuts down cleanly and exits 2: the test did not happen.
  marker.py --mode check --expect absent|present --evidence DIR
      IPL; job OSECHK LISTCATs the marker: CC 0004 means absent, 0000 present;
      clean shutdown. Exit 0 only if the result is the expected one.
Credentials come from GUEST_USER/GUEST_PASS and are redacted from saved files.
Reuses the OSE-003 drivers (mvs-smoke.py) and the OSE-004 deck helpers unchanged.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

LIB = Path("/ose/scripts/lib")
HELLO_GUEST = Path("/ose/tests/guest/hello/hello_guest.py")

CREATE = """//OSEMARK  JOB (OSE),'OSE-009 MARKER',CLASS=A,MSGCLASS=A,
//             MSGLEVEL=(1,1),USER={USER},PASSWORD={PASS}
//DEL      EXEC PGM=IDCAMS
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  DELETE {DSN} NONVSAM SCRATCH PURGE
  SET MAXCC=0
/*
//MAKE     EXEC PGM=IEFBR14,COND=(0,NE,DEL)
//MARK     DD  DSN={DSN},DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,SPACE=(TRK,(1,1)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=800)
//SHOW     EXEC PGM=IDCAMS,COND=((0,NE,DEL),(0,NE,MAKE))
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  LISTCAT ENTRIES({DSN})
/*
//
"""

CHECK = """//OSECHK   JOB (OSE),'OSE-009 CHECK',CLASS=A,MSGCLASS=A,
//             MSGLEVEL=(1,1),USER={USER},PASSWORD={PASS}
//LOOK     EXEC PGM=IDCAMS
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  LISTCAT ENTRIES({DSN})
/*
//
"""


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--mode", choices=("create-hold", "check"), required=True)
    a.add_argument("--expect", choices=("absent", "present"))
    a.add_argument("--hold", type=int, default=900)
    a.add_argument("--mvsce", type=Path, default=Path("/work/sysgen/MVSCE"))
    a.add_argument("--evidence", type=Path, required=True)
    args = a.parse_args()
    if args.mode == "check" and not args.expect:
        a.error("--mode check needs --expect")
    user, pw = os.environ["GUEST_USER"], os.environ["GUEST_PASS"]
    ev = args.evidence
    ev.mkdir(parents=True, exist_ok=True)
    smoke = load("mvs_smoke", LIB / "mvs-smoke.py")
    hg = load("hello_guest", HELLO_GUEST)
    values = {"USER": user, "PASS": pw, "DSN": f"{user}.OSE009.MARKER"}
    result = {"mode": args.mode, "dsn": values["DSN"]}
    ok = True
    killed_expected = False
    t0 = time.time()
    h = smoke.Herc(args.mvsce, ev / f"{args.mode}-hercules.log")
    try:
        for _mid, rx in smoke.IPL_SEQUENCE:
            h.wait(rx, smoke.IPL_TIMEOUT)
        result["ipl_seconds"] = round(time.time() - t0)
        print(f"IPL complete after {result['ipl_seconds']}s", flush=True)
        h.send("/$S PRT1")
        h.wait(r"\$HASP(160|170|000).*PRINTER1|\$HASP150|PRINTER1", 60)
        if args.mode == "create-hold":
            good, _ = hg.run_job(smoke, h, args.mvsce, "OSEMARK", b"".join(hg.jcl_cards(hg.fill(CREATE, values))),
                                 {"DEL": "0000", "MAKE": "0000", "SHOW": "0000"}, result)
            if not good:
                raise RuntimeError("marker was not created")
            (ev / "marker-created").write_text(values["DSN"] + "\n")
            print(f"marker {values['DSN']} created; holding up to {args.hold}s for kill -9", flush=True)
            killed_expected = True
            end = time.time() + args.hold
            while time.time() < end:
                if h.p.poll() is not None:
                    raise RuntimeError(f"hercules exited by itself (rc {h.p.returncode}) during the hold")
                h._poll()
                time.sleep(2)
            ok = False
            result["error"] = "not killed within the hold time"
        else:
            want = {"absent": "0004", "present": "0000"}[args.expect]
            good, text = hg.run_job(smoke, h, args.mvsce, "OSECHK", b"".join(hg.jcl_cards(hg.fill(CHECK, values))),
                                    {"LOOK": want}, result)
            rcs = dict(smoke.step_rcs(args.mvsce / "printers" / "prt00e.txt", "OSECHK"))
            state = {"0000": "present", "0004": "absent"}.get(rcs.get("LOOK"), f"unknown ({rcs.get('LOOK')})")
            result["marker"] = state
            print(f"OSECHK: marker {values['DSN']} is {state} (expected {args.expect})", flush=True)
            ok &= good and state == args.expect
    except Exception as e:  # noqa: BLE001
        ok = False
        result["error"] = str(e)
        print(f"ERROR {e}", file=sys.stderr, flush=True)
    finally:
        rc = h.stop()
        mark = h.stop_mark if h.stop_mark is not None else len(h.console)
        stopped, missing = smoke.shutdown_check(h.console, mark)
        result.update(hercules_rc=rc, shutdown_messages=stopped, shutdown_missing=missing,
                      total_seconds=round(time.time() - t0))
        if h.quit_fallback or rc != 0 or h.exited_early or missing:
            ok = False
        red = lambda s: s.replace(pw, "<redacted>")  # noqa: E731
        (ev / f"{args.mode}-mvslog.txt").write_text(red("\n".join(h.console)) + "\n", encoding="utf-8")
        (ev / f"{args.mode}-prt00e.txt").write_text(red(hg.printer_text(args.mvsce)), encoding="utf-8")
        result["ok"] = bool(ok)
        (ev / f"{args.mode}-result.json").write_text(red(json.dumps(result, indent=1)) + "\n", encoding="utf-8")
        print(f"{args.mode}: ok={ok} hercules rc={rc} shutdown_missing={missing}", flush=True)
    sys.exit(0 if ok else (2 if killed_expected else 1))


if __name__ == "__main__":
    main()

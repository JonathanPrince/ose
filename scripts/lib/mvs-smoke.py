"""OSE-003 tests 3-4: cold IPL of the built MVS/CE, JES2 smoke job, clean shutdown.

Runs inside the Hercules image (scripts/smoke.sh calls it), in the MVSCE/
directory produced by sysgen. Modelled on sysgen.py's own automation (at the
pin: Popen of `hercules --externalgui`, waiting for console strings, card
reader socket on 3505, `script SCRIPTS/SHUTDOWN.RC` for shutdown), because
sysgen.py cannot be imported (it calls main() at module level).

Usage: python3 -I mvs-smoke.py --mvsce DIR --evidence DIR --tag NAME [--jes2 JOB.jcl]
           [--user U --password P] [--tso CMD]
Exit 0 only if every expected message and RC was observed.
"""
import argparse
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

IPL_DONE = "$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE"
IPL_TIMEOUT = 900
JOB_TIMEOUT = 600
STOP_TIMEOUT = 300


class Herc:
    def __init__(self, mvsce: Path, log: Path):
        self.log = log.open("w", encoding="utf-8", errors="replace")
        self.q = queue.Queue()
        self.lines = []
        self.p = subprocess.Popen(
            ["hercules", "--externalgui", "-f", "conf/local.cnf", "-r", "conf/mvsce.rc"],
            cwd=mvsce, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="replace")
        for s in (self.p.stdout, self.p.stderr):
            threading.Thread(target=self._read, args=(s,), daemon=True).start()

    def _read(self, stream):
        for line in stream:
            line = line.rstrip("\n")
            self.log.write(f"{time.strftime('%H:%M:%S')} {line}\n")
            self.log.flush()
            self.q.put(line)

    def wait(self, pattern, timeout):
        rx = re.compile(pattern)
        end = time.time() + timeout
        while time.time() < end:
            try:
                line = self.q.get(timeout=1)
            except queue.Empty:
                if self.p.poll() is not None:
                    raise RuntimeError(f"hercules exited (rc {self.p.returncode}) waiting for {pattern!r}")
                continue
            self.lines.append(line)
            m = rx.search(line)
            if m:
                return line
        raise TimeoutError(f"no {pattern!r} within {timeout}s")

    def send(self, cmd):
        self.log.write(f"{time.strftime('%H:%M:%S')} >>> {cmd}\n")
        self.p.stdin.write(cmd + "\n")
        self.p.stdin.flush()

    def stop(self):
        if self.p.poll() is None:
            self.send("script SCRIPTS/SHUTDOWN.RC")
            try:
                self.p.wait(STOP_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.send("quit")
                self.p.wait(60)
        self.log.close()
        return self.p.returncode


def submit(jcl: str, port=3505):
    with socket.create_connection(("127.0.0.1", port), timeout=30) as s:
        s.sendall(jcl.encode("ascii"))


def step_rcs(printer: Path, jobname: str):
    """IEF142I lines of the job from the JES2 printer file: [(step, code), ...]."""
    text = printer.read_text(encoding="ascii", errors="replace") if printer.exists() else ""
    rx = re.compile(rf"IEF142I\s+{re.escape(jobname)}\s+(\S+)\s+-\s+STEP WAS EXECUTED\s+-\s+COND CODE\s+(\d{{4}})")
    return rx.findall(text)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--mvsce", type=Path, required=True)
    a.add_argument("--evidence", type=Path, required=True)
    a.add_argument("--tag", required=True)
    a.add_argument("--jes2", type=Path)
    a.add_argument("--expect", default="", help="step=code,step=code expected in the job")
    a.add_argument("--user")
    a.add_argument("--password")
    a.add_argument("--hold-for-tso", type=int, default=0, help="seconds to keep MVS up after JES2 (TSO smoke)")
    args = a.parse_args()
    ev = args.evidence
    ev.mkdir(parents=True, exist_ok=True)
    result = {"tag": args.tag}
    t0 = time.time()
    h = Herc(args.mvsce, ev / f"{args.tag}-hercules.log")
    ok = True
    try:
        line = h.wait(re.escape(IPL_DONE), IPL_TIMEOUT)
        result["ipl_seconds"] = round(time.time() - t0)
        result["ipl_done"] = line
        ids = sorted({m.group(0) for l in h.lines for m in [re.search(r"\$?(HASP|IEE|IEF|IST|IKT|IEA)\d{3,4}[IAED]?", l)] if m})
        result["message_ids_seen"] = ids
        print(f"{args.tag}: IPL complete after {result['ipl_seconds']}s: {line.strip()}")

        if args.jes2:
            jcl = args.jes2.read_text(encoding="ascii")
            job = re.match(r"//(\S+)\s+JOB", jcl).group(1)
            if args.user:
                jcl = jcl.replace("USER=&USER", f"USER={args.user}").replace("PASSWORD=&PASS", f"PASSWORD={args.password}")
            submit(jcl)
            print(f"{args.tag}: submitted {job}")
            ended = h.wait(rf"\$HASP395\s+{re.escape(job)}\s+ENDED", JOB_TIMEOUT)
            print(f"{args.tag}: {ended.strip()}")
            printer = args.mvsce / "printers" / "prt00e.txt"
            rcs = []
            for _ in range(60):            # the printer writes after the job ends
                rcs = step_rcs(printer, job)
                if len(rcs) >= len([e for e in args.expect.split(",") if e]):
                    break
                time.sleep(2)
            result["job"] = job
            result["step_rcs"] = rcs
            want = dict(e.split("=") for e in args.expect.split(",") if e)
            got = dict(rcs)
            result["expected"] = want
            for step, code in want.items():
                status = "ok" if got.get(step) == code else "MISMATCH"
                ok &= status == "ok"
                print(f"{args.tag}: step {step} expected {code} got {got.get(step)} {status}")
        if args.hold_for_tso:
            (ev / f"{args.tag}-ready").write_text("ready\n")
            print(f"{args.tag}: holding {args.hold_for_tso}s for the TSO smoke")
            end = time.time() + args.hold_for_tso
            while time.time() < end and not (ev / f"{args.tag}-tso-done").exists():
                time.sleep(2)
    except Exception as e:  # noqa: BLE001 - report every failure as evidence
        ok = False
        result["error"] = str(e)
        print(f"{args.tag}: ERROR {e}", file=sys.stderr)
    finally:
        rc = h.stop()
        result["hercules_rc"] = rc
        result["total_seconds"] = round(time.time() - t0)
        (ev / f"{args.tag}-result.txt").write_text("\n".join(f"{k}: {v}" for k, v in result.items()) + "\n")
        print(f"{args.tag}: hercules rc={rc}, total {result['total_seconds']}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

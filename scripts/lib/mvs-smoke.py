"""OSE-003 tests 3-4: cold IPL of the built MVS/CE, JES2 smoke job, clean shutdown.

Runs inside the Hercules image (scripts/smoke.sh calls it), in the MVSCE/
directory produced by sysgen. Modelled on sysgen.py's own automation at the pin
(Popen of `hercules --externalgui`, operator commands as "/cmd" on stdin, the
card reader socket on 3505, `script SCRIPTS/SHUTDOWN.RC` for shutdown);
sysgen.py itself cannot be imported (it calls main() at module level).

Observed on the first run (2026-11-26): in the finished MVS/CE the MVS console
messages do not reach Hercules' stdout. They go to the master console and to its
hardcopy printer 0015 = MVSCE/mvslog.txt, so this script follows that file. The
build-time marker "$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE" does not appear at
IPL; IPL completion is the sequence IPL_SEQUENCE below, taken from that log.

Usage: python3 -I mvs-smoke.py --mvsce DIR --evidence DIR --tag NAME
           [--jes2 JOB.jcl --expect STEP=RC,... --user U --password P] [--hold-for-tso SECONDS]
Exit 0 only if every expected message and RC was observed and shutdown was clean.
"""
import argparse
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# (message ID, regex) in the order they appear during a successful IPL
IPL_SEQUENCE = [
    ("IEA101A", r"IEA101A SPECIFY SYSTEM PARAMETERS"),         # NIP
    ("$HASP493", r"\$HASP493 JES2 +\S+-START IS IN PROGRESS"),  # JES2 starting
    ("IEE041I", r"IEE041I THE SYSTEM LOG IS NOW ACTIVE"),
    ("IST020I", r"IST020I +VTAM INITIALIZATION COMPLETE"),
    ("IKT007I", r"IKT007I TCAS ACCEPTING LOGONS"),               # TSO ready
]
IPL_TIMEOUT = 900
JOB_TIMEOUT = 600
STOP_TIMEOUT = 420


class Herc:
    def __init__(self, mvsce: Path, log: Path):
        self.mvsce = mvsce
        self.hardcopy = mvsce / "mvslog.txt"
        for f in (self.hardcopy, mvsce / "printers" / "prt00e.txt"):
            f.unlink(missing_ok=True)          # fresh files for this IPL
        self.offset = 0
        self.buf = ""
        self.console = []                      # every hardcopy line seen
        self.log = log.open("w", encoding="utf-8", errors="replace")
        self.p = subprocess.Popen(
            ["hercules", "--externalgui", "-f", "conf/local.cnf", "-r", "conf/mvsce.rc"],
            cwd=mvsce, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace")
        threading.Thread(target=self._drain, daemon=True).start()
        self.quit_fallback = False

    def _drain(self):
        for line in self.p.stdout:
            if not re.match(r"(DEV[ACX]|STATUS|MIPS|SIOS|SYS|CPUPCT|POS|SIZE)=", line):
                self.log.write(f"{time.strftime('%H:%M:%S')} {line}")
                self.log.flush()

    def _poll(self):
        if not self.hardcopy.exists():
            return []
        with self.hardcopy.open("rb") as f:
            f.seek(self.offset)
            data = f.read()
        self.offset += len(data)
        self.buf += data.decode("latin-1")
        *lines, self.buf = self.buf.split("\n")
        lines = ["".join(ch for ch in l if ch.isprintable()).strip() for l in lines]
        self.console += lines
        return lines

    def wait(self, pattern, timeout):
        rx = re.compile(pattern)
        for l in self.console:                  # already seen
            if rx.search(l):
                return l
        end = time.time() + timeout
        while time.time() < end:
            for l in self._poll():
                if rx.search(l):
                    return l
            if self.p.poll() is not None:
                raise RuntimeError(f"hercules exited (rc {self.p.returncode}) waiting for {pattern!r}")
            time.sleep(1)
        raise TimeoutError(f"no {pattern!r} in mvslog.txt within {timeout}s")

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
                self.quit_fallback = True
                self.send("quit")
                self.p.wait(60)
        self._poll()
        self.log.close()
        return self.p.returncode


def submit(jcl: str, port=3505):
    with socket.create_connection(("127.0.0.1", port), timeout=30) as s:
        s.sendall(jcl.encode("ascii"))


def step_rcs(printer: Path, jobname: str):
    """IEF142I lines of the job from the JES2 printer file: [(step, code), ...]."""
    text = printer.read_text(encoding="latin-1") if printer.exists() else ""
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
    a.add_argument("--hold-for-tso", type=int, default=0, help="seconds to keep MVS up for the TSO smoke")
    args = a.parse_args()
    ev = args.evidence
    ev.mkdir(parents=True, exist_ok=True)
    result = {"tag": args.tag}
    ok = True
    t0 = time.time()
    h = Herc(args.mvsce, ev / f"{args.tag}-hercules.log")
    try:
        seen = []
        for mid, rx in IPL_SEQUENCE:
            line = h.wait(rx, IPL_TIMEOUT)
            seen.append(f"{mid} +{round(time.time() - t0)}s: {line}")
        result["ipl_seconds"] = round(time.time() - t0)
        result["ipl_sequence"] = seen
        print(f"{args.tag}: IPL complete after {result['ipl_seconds']}s")
        for s in seen:
            print(f"{args.tag}:   {s}")

        if args.jes2:
            h.send("/$S PRT1")                  # PRINTER1 (class A) is INACTIVE after IPL
            h.wait(r"\$HASP(160|170|000).*PRINTER1|\$HASP150|PRINTER1", 60)
            jcl = args.jes2.read_text(encoding="ascii")
            job = re.match(r"//(\S+)\s+JOB", jcl).group(1)
            if args.user:
                jcl = jcl.replace("USER=&USER", f"USER={args.user}").replace("PASSWORD=&PASS", f"PASSWORD={args.password}")
            submit(jcl)
            print(f"{args.tag}: submitted {job}")
            ended = h.wait(rf"\$HASP395\s+{re.escape(job)}\s+ENDED", JOB_TIMEOUT)
            print(f"{args.tag}: {ended}")
            want = dict(e.split("=") for e in args.expect.split(",") if e)
            printer = args.mvsce / "printers" / "prt00e.txt"
            rcs = []
            for _ in range(90):                 # the printer writes after the job ends
                rcs = step_rcs(printer, job)
                if len(rcs) >= len(want):
                    break
                time.sleep(2)
            got = dict(rcs)
            result.update(job=job, job_ended=ended, step_rcs=rcs, expected=want)
            for step, code in want.items():
                status = "ok" if got.get(step) == code else "MISMATCH"
                ok &= status == "ok"
                print(f"{args.tag}: step {step} expected {code} got {got.get(step)} {status}")
        if args.hold_for_tso:
            (ev / f"{args.tag}-ready").write_text("ready\n")
            print(f"{args.tag}: holding up to {args.hold_for_tso}s for the TSO smoke")
            end = time.time() + args.hold_for_tso
            while time.time() < end and not (ev / f"{args.tag}-tso-done").exists():
                h._poll()
                time.sleep(2)
    except Exception as e:  # noqa: BLE001 - every failure is evidence
        ok = False
        result["error"] = str(e)
        print(f"{args.tag}: ERROR {e}", file=sys.stderr)
    finally:
        rc = h.stop()
        stopped = [l for l in h.console if re.search(r"IEE334I|\$HASP085|\$HASP099", l)]
        result.update(hercules_rc=rc, quit_fallback=h.quit_fallback, shutdown_messages=stopped,
                      total_seconds=round(time.time() - t0))
        if h.quit_fallback or rc != 0:
            ok = False
        (ev / f"{args.tag}-mvslog.txt").write_text("\n".join(h.console) + "\n", encoding="utf-8")
        (ev / f"{args.tag}-result.txt").write_text("\n".join(f"{k}: {v}" for k, v in result.items()) + "\n")
        print(f"{args.tag}: hercules rc={rc} quit_fallback={h.quit_fallback} shutdown={stopped} total {result['total_seconds']}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

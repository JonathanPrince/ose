"""OSE-003 test 5: automated TSO logon as a non-admin user, one command with
checked output, logoff. Uses s3270 4.1ga10 (Debian main, in the tools image).

Runs in the same container as mvs-smoke.py while it holds MVS up. Credentials
come from the environment (TSO_USER, TSO_PASS), which scripts/smoke.sh reads
from upstream users.conf in the leased volume; the password is redacted from
every saved screen and from the s3270 log. Every screen is saved to
evidence/tso-NN-<label>.txt.

Dialogue (observed on MVS/CE built from sysgen 4746195d, 2026-11-26):
  1. Hercules 3270 logo, "CLEAR the screen or hit ENTER"  -> Enter
  2. VTAM screen "TSO Logon ===>"                         -> LOGON user/password
  3. MVS/CE welcome banner ending in READY                 -> TIME
  4. " TIME-hh:mm:ss PM. CPU-..." (no message ID on 3.8j)   -> LOGOFF
  5. the terminal returns to a logon screen (or IKJ56470I)
Exit 0 only if READY, the TIME output and the logoff were all seen.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path


class S3270:
    def __init__(self, log: Path):
        self.p = subprocess.Popen(["s3270", "-utf8"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True)
        self.log = log.open("w", encoding="utf-8")

    def do(self, action, secret=False):
        self.log.write(f">>> {'String(<redacted>)' if secret else action}\n")
        self.p.stdin.write(action + "\n")
        self.p.stdin.flush()
        data = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("s3270 exited")
            line = line.rstrip("\n")
            if line in ("ok", "error"):
                self.log.write(f"<<< {line}\n")
                self.log.flush()
                return line == "ok", data
            if line.startswith("data: "):
                data.append(line[6:])

    def screen(self):
        ok, data = self.do("Ascii()")
        return "\n".join(data)

    def close(self):
        try:
            self.do("Disconnect()")
            self.do("Quit()")
        except Exception:  # noqa: BLE001
            pass
        self.log.close()


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--evidence", type=Path, required=True)
    a.add_argument("--host", default="127.0.0.1:3270")
    a.add_argument("--timeout", type=int, default=300)
    args = a.parse_args()
    user, pw = os.environ["TSO_USER"], os.environ["TSO_PASS"]
    ev = args.evidence
    ev.mkdir(parents=True, exist_ok=True)
    n = 0
    t = S3270(ev / "tso-s3270.log")

    def snap(label):
        nonlocal n
        scr = t.screen()
        n += 1
        (ev / f"tso-{n:02d}-{label}.txt").write_text(scr.replace(pw, "<redacted>") + "\n", encoding="utf-8")
        return scr

    def wait_for(pattern, label, timeout=60, poke=None):
        """Poll the screen for pattern. Press Enter only when the screen matches
        poke (e.g. a '***' continuation prompt): an Enter while TSO is still
        processing the logon blanked the screen on the 2026-11-26 run."""
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
        raise TimeoutError(f"{label}: no {pattern!r} within {timeout}s")

    seen = {"ready": False, "time": False, "logoff": False}
    try:
        end = time.time() + args.timeout
        ok = False
        while time.time() < end and not ok:      # the terminal port accepts after IPL
            ok, _ = t.do(f"Connect({args.host})")
            if not ok:
                time.sleep(5)
        if not ok:
            raise RuntimeError(f"cannot connect to {args.host}")
        t.do("Wait(60,InputField)")
        snap("connected")                        # Hercules logo
        t.do("Enter()")
        wait_for(r"TSO Logon ===>", "vtam-logon", poke=r"CLEAR the screen or hit ENTER")
        t.do(f'String("LOGON {user}/{pw}")', secret=True)
        t.do("Enter()")
        wait_for(r"^\s*READY\s*$", "ready", timeout=120, poke=r"\*\*\*\s*$")
        seen["ready"] = True
        t.do("Clear()")
        t.do('String("TIME")')
        t.do("Enter()")
        # MVS 3.8j prints no message ID here (observed 2026-11-26):
        # " TIME-05:42:26 PM. CPU-00:00:00 SERVICE-208 SESSION-00:00:01 NOVEMBER 26,2026"
        wait_for(r"^\s*TIME-\d\d:\d\d:\d\d [AP]M\. CPU-", "time")
        seen["time"] = True
        t.do('String("LOGOFF")')
        t.do("Enter()")
        wait_for(r"IKJ56470I|TSO Logon ===>|CLEAR the screen or hit ENTER", "logoff", timeout=60)
        seen["logoff"] = True
    except Exception as e:  # noqa: BLE001
        print(f"tso-smoke: ERROR {e}", file=sys.stderr)
    finally:
        t.close()
    print(f"tso-smoke: user={user} ready={seen['ready']} time={seen['time']} logoff={seen['logoff']}")
    (ev / "tso-result.txt").write_text("\n".join(f"{k}: {v}" for k, v in seen.items()) + "\n")
    sys.exit(0 if all(seen.values()) else 1)


if __name__ == "__main__":
    main()

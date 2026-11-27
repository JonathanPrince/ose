"""Host tests for the OSE-004 guest driver's pure logic (tests/guest/hello/hello_guest.py):
deck building for the EBCDIC reader, DLM choice, template filling, LISTDS parsing and
the fail-closed shape of the deploy JCL. No guest, no Docker."""
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("hello_guest", ROOT / "tests" / "guest" / "hello" / "hello_guest.py")
hg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hg)
hg.JCL = ROOT / "jcl" / "hello"
VALUES = {"USER": "TUSER", "PASS": "SECRET1", "HLQ": "TUSER", "VOLUME": "PUB000"}


def cards(deck):
    return [deck[i:i + 80] for i in range(0, len(deck), 80)]


class Deck(unittest.TestCase):
    def test_fill_rejects_leftover_placeholders(self):
        with self.assertRaises(ValueError):
            hg.fill("A {USER} {OTHER}", {"USER": "x"})
        self.assertEqual(hg.fill("A {USER}", {"USER": "x"}), "A x")

    def test_jcl_cards_are_80_byte_cp037(self):
        c = hg.jcl_cards("//X JOB\n  DATA")
        self.assertEqual([len(x) for x in c], [80, 80])
        self.assertEqual(c[0][:7].decode("cp037"), "//X JOB")

    def test_jcl_statement_past_column_71_rejected(self):
        with self.assertRaises(ValueError):
            hg.jcl_cards("//" + "X" * 70)
        hg.jcl_cards("//*" + "X" * 70)          # comments may use 72-80

    def test_dlm_avoids_record_starts(self):
        recs = ["@@".encode("cp037") + bytes(78), "$$".encode("cp037") + bytes(78)]
        self.assertEqual(hg.choose_dlm(recs), "##")

    def test_deploy_deck_embeds_xmit_verbatim(self):
        xmit = bytes(range(256)) * 5 + bytes(80 * 4 - 256 * 5 % 80)     # binary, multiple of 80
        xmit = xmit[: len(xmit) - len(xmit) % 80]
        deck = hg.deploy_deck(xmit, VALUES)
        self.assertEqual(len(deck) % 80, 0)
        self.assertIn(xmit, deck)
        cs = cards(deck)
        text = [c.decode("cp037").rstrip() for c in cs]
        i = text.index(next(t for t in text if t.startswith("//SYSUT1   DD  DATA,DLM=")))
        dlm = text[i].split("DLM=")[1]
        n = len(xmit) // 80
        self.assertEqual(b"".join(cs[i + 1:i + 1 + n]), xmit)
        self.assertEqual(text[i + 1 + n], dlm)
        self.assertFalse(any(re.search(r"\{[A-Z]+\}", t) for t in text[:i] + text[i + 1 + n:]))

    def test_deploy_deck_rejects_partial_record(self):
        with self.assertRaises(ValueError):
            hg.deploy_deck(bytes(81), VALUES)

    def test_password_only_on_job_card(self):
        deck = hg.text_deck("run.jcl", VALUES)
        text = [c.decode("cp037") for c in cards(deck)]
        self.assertEqual([i for i, t in enumerate(text) if "SECRET1" in t], [1])


class DeployJcl(unittest.TestCase):
    """The deploy must fail closed: RECEIVE only into a library that is gone."""

    def setUp(self):
        self.jcl = (ROOT / "jcl" / "hello" / "deploy.jcl").read_text()

    def step_order(self):
        return re.findall(r"^//(\w+)\s+EXEC", self.jcl, re.M)

    def test_gone_check_precedes_stage(self):
        self.assertEqual(self.step_order(), ["DELOLD", "GONE", "STAGE", "RECV", "CLEANUP"])
        self.assertRegex(self.jcl, r"//STAGE\s+EXEC PGM=IEBGENER,COND=\(\(0,NE,DELOLD\),\(4,NE,GONE\)\)")
        # R04-2: MVS ignores a COND test naming a bypassed step, so RECV and
        # CLEANUP must test DELOLD and GONE themselves, not only STAGE.
        for step in ("RECV", "CLEANUP"):
            m = re.search(rf"//{step}\s+EXEC [^\n]*\n(//\s+COND=[^\n]*)", self.jcl)
            self.assertIsNotNone(m, step)
            self.assertIn("(0,NE,DELOLD)", m.group(1), step)
            self.assertIn("(4,NE,GONE)", m.group(1), step)

    def test_jcl_columns(self):
        for n, line in enumerate(self.jcl.splitlines(), 1):
            if line.startswith("//") and not line.startswith("//*"):
                self.assertLessEqual(len(line), 71, f"line {n}")

    def test_stale_variant_drops_only_the_target_delete(self):
        xmit = bytes(80 * 3)
        normal = [c.decode("cp037").rstrip() for c in cards(hg.deploy_deck(xmit, VALUES))]
        stale = [c.decode("cp037").rstrip() for c in cards(hg.deploy_deck(xmit, VALUES, omit_target_delete=True))]
        self.assertIn("  DELETE TUSER.OSE.LOAD NONVSAM SCRATCH PURGE", normal)
        self.assertNotIn("  DELETE TUSER.OSE.LOAD NONVSAM SCRATCH PURGE", stale)
        self.assertTrue(stale[0].startswith("//OSEHSTL  JOB"))
        self.assertEqual(len(normal) - len(stale), 1)

    def test_driver_expects_gone_rc4(self):
        src = (ROOT / "tests" / "guest" / "hello" / "hello_guest.py").read_text()
        self.assertIn('"GONE": "0004"', src)


class Spool(unittest.TestCase):
    LISTDS = """
  LISTDS 'MVSCE02.OSE.LOAD' MEMBERS
MVSCE02.OSE.LOAD
--RECFM-LRECL-BLKSIZE-DSORG
  U     **    15040   PO
--VOLUMES--
  PUB000
--MEMBERS--
  HELLO
END
"""

    def test_members_listed(self):
        self.assertEqual(hg.members_listed(self.LISTDS, "MVSCE02.OSE.LOAD"), ["HELLO"])
        self.assertEqual(hg.members_listed(self.LISTDS, "OTHER.DSN"), [])

    def test_no_members_section(self):
        self.assertEqual(hg.members_listed("MVSCE02.OSE.LOAD\nIKJ58503I DATA SET NOT IN CATALOG\n",
                                           "MVSCE02.OSE.LOAD"), [])

    def test_hello_line_is_exact(self):
        self.assertTrue(hg.HELLO_LINE.match("OSE-004 HELLO RC=4"))
        self.assertFalse(hg.HELLO_LINE.match("//RC4 EXEC PGM=HELLO,PARM='4' OSE-004 HELLO RC=4"))

    def test_job_failures(self):
        t = "IEF452I OSEHRUN - JOB NOT RUN - JCL ERROR\nIEF450I OSEHRUN RC0 - ABEND S0C4 U0000\n"
        self.assertEqual(len(hg.job_failures(t, "OSEHRUN")), 2)
        self.assertEqual(hg.job_failures(t, "OSEHDEP"), [])


FAKE_DOCKER = r"""#!/bin/sh
# fake docker for DeployExport; FAKE_MODE = export-fails | export-short | ok
echo "$*" >> "$FAKE_LOG"
case "$1" in
  image) exit 0 ;;
  rm) exit 0 ;;
  wait) echo 0; exit 0 ;;
  logs) echo "fake guest console"; exit 0 ;;
  run)
    case "$*" in
      "run -d "*) exit 0 ;;          # the detached guest container
      *awk*) echo "MVSCE02 FAKEPW1"; exit 0 ;;
      *"cp -R"*)
        [ "$FAKE_MODE" = export-fails ] && { echo "cp: simulated failure" >&2; exit 1; }
        out=$(printf '%s\n' "$@" | sed -n 's#^\(.*\):/out$#\1#p' | head -1)
        mode=$(eval "echo \${$#}")
        mkdir -p "$out/$mode"
        [ "$FAKE_MODE" = ok ] && printf x > "$out/$mode/a.txt" && printf y > "$out/$mode/b.txt"
        exit 0 ;;
      *python3*) # the guest-side manifest: a.txt = "x", b.txt = "y". Two lines, so a
                 # host manifest joined with CRLF (Windows print) would not match.
        echo "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881  a.txt"
        echo "a1fce4363854ff888cff4b8e7875d600c2682390412a8cf79b37d0b11148b0fa  b.txt"; exit 0 ;;
      *"rm -rf"*) echo "GUEST-COPY-DELETED" >> "$FAKE_LOG"; exit 0 ;;
      *) exit 0 ;;   # package-pin verification
    esac ;;
esac
exit 0
"""


def find_bash():
    import os
    import shutil
    if os.environ.get("OSE_BASH"):
        return os.environ["OSE_BASH"]
    b = shutil.which("bash")
    if b and "system32" not in b.lower():
        return b
    for c in (r"C:\Program Files\Git\bin\bash.exe",):
        if Path(c).exists():
            return c
    return None


BASH = find_bash()


@unittest.skipUnless(BASH, "bash not found (set OSE_BASH)")
class DeployExport(unittest.TestCase):
    """R04-3: deploy.sh must fail when its evidence export fails or is incomplete,
    and must keep the guest copy until a verified export."""

    def run_deploy(self, mode):
        import os
        import shutil
        import stat
        import subprocess
        import sys
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        d = tmp / "bin" / "docker"
        d.parent.mkdir()
        d.write_text(FAKE_DOCKER, newline="\n")
        d.chmod(d.stat().st_mode | stat.S_IEXEC)
        log = tmp / "docker.log"
        posix = lambda p: str(p).replace("\\", "/")  # noqa: E731
        env = dict(os.environ, FAKE_MODE=mode, FAKE_LOG=posix(log), PYTHON=posix(Path(sys.executable)),
                   OSE004_EVIDENCE_ROOT=posix(tmp / "ev"), DASD_VOLUME="fake-volume")
        cmd = (f'PATH="$(cygpath -u "{posix(d.parent)}" 2>/dev/null || echo "{posix(d.parent)}"):$PATH" '
               f'sh "{posix(ROOT)}/scripts/deploy.sh" run')
        p = subprocess.run([BASH, "-c", cmd], env=env, capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr, log.read_text() if log.exists() else ""

    def test_export_failure_fails_and_keeps_guest_copy(self):
        rc, out, log = self.run_deploy("export-fails")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("EVIDENCE: export", out)
        self.assertNotIn("GUEST-COPY-DELETED", log)

    def test_incomplete_export_fails_and_keeps_guest_copy(self):
        rc, out, log = self.run_deploy("export-short")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("differs from the guest copy", out)
        self.assertNotIn("GUEST-COPY-DELETED", log)

    def test_verified_export_passes_then_deletes_guest_copy(self):
        rc, out, log = self.run_deploy("ok")
        self.assertEqual(rc, 0, out)
        self.assertIn("exported and verified (2 files)", out)
        self.assertIn("GUEST-COPY-DELETED", log)
        self.assertNotIn("FAKEPW1", out)


if __name__ == "__main__":
    unittest.main()

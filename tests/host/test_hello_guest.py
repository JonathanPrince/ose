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
        self.assertRegex(self.jcl, r"//RECV\s+EXEC .*COND=\(0,NE,STAGE\)")

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


if __name__ == "__main__":
    unittest.main()

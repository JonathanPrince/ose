"""Host tests for the OSE-011 listing driver (tests/guest/audit/run_listing.py):
LISTDS member and alias parsing (formats observed on MVS/CE 2026-11-27), user
library qualification, credentials, the IEFJSSNT decode and the collision table.
No guest, no Docker."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("run_listing", ROOT / "tests" / "guest" / "audit" / "run_listing.py")
rl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rl)
JCL = (ROOT / "jcl" / "audit" / "list-libraries.jcl").read_text()

SPOOL = """ LISTDS 'SYS1.CMDLIB' MEMBERS
SYS1.CMDLIB
--RECFM-LRECL-BLKSIZE-DSORG
  U     **    19069   PO
--VOLUMES--
  MVSRES
--MEMBERS--
  ADDSD  ALIAS(AD,RDEF,RDEFINE)
  IDCAM01  ALIAS(ALTER,DEF,DEFINE,DEL,DELETE,
  EXP,EXPORT,IMP,IMPORT,LISTC,LISTCAT,PRINT,
  REPRO,VERIFY,VFY)
  IGC0013{  ALIAS(IGC0013A)
  TIME
 LISTDS 'SYS2.CMDPROC' MEMBERS
SYS2.CMDPROC
--RECFM-LRECL-BLKSIZE-DSORG
  FB    80    19040   PO
--VOLUMES--
  MVS000
--MEMBERS--
 LISTDS 'MVSCE02.CLIST' MEMBERS
IKJ58503I DATA SET MVSCE02.CLIST NOT IN CATALOG
END
"""


class Parse(unittest.TestCase):
    def test_members_and_multiline_aliases(self):
        sec = rl.listds_sections(SPOOL, ["SYS1.CMDLIB", "SYS2.CMDPROC", "MVSCE02.CLIST", "ABSENT.LIB"])
        kind, names = sec["SYS1.CMDLIB"]
        self.assertEqual(kind, "members")
        for n in ("ADDSD", "AD", "RDEFINE", "IDCAM01", "DELETE", "LISTCAT", "VFY", "IGC0013{", "IGC0013A", "TIME"):
            self.assertIn(n, names)
        self.assertFalse([n for n in names if n.startswith("?")])
        self.assertEqual(sec["SYS2.CMDPROC"], ("members", []))
        self.assertEqual(sec["MVSCE02.CLIST"][0], "error")
        self.assertEqual(sec["ABSENT.LIB"], ("missing", []))

    def test_unparsable_line_is_kept_visible(self):
        self.assertEqual(rl.parse_members(["  GOOD", "  not a member line"]), ["GOOD", "?not a member line"])

    def test_collision_found_through_alias(self):
        sec = {"SYS1.CMDLIB": ("members", rl.parse_members(["  REAL  ALIAS(OSH,OTHER)"]))}
        row = next(r for r in rl.collisions(sec) if r["name"] == "OSH")
        self.assertEqual(row["found_in"], ["SYS1.CMDLIB"])


class Job(unittest.TestCase):
    def test_credentials_only_on_job_card(self):
        j = rl.add_credentials(JCL, "TUSER", "SECRET1")
        lines = [n for n, l in enumerate(j.splitlines()) if "SECRET1" in l]
        self.assertEqual(lines, [1])
        self.assertLessEqual(len(j.splitlines()[1]), 71)

    def test_user_libraries_qualified(self):
        q = rl.qualify_user_libraries(JCL, "TUSER")
        cmds = rl.listds_commands(q)
        self.assertIn("TUSER.CLIST", cmds)
        self.assertIn("TUSER.EXEC", cmds)
        self.assertNotIn("CLIST", cmds)
        self.assertIn("SYS1.LINKLIB", cmds)

    def test_every_step_runs_even_after_a_failure(self):
        import re
        steps = re.findall(r"^//(\w+)\s+EXEC ([^\n]*)", JCL, re.M)
        self.assertEqual([s for s, _ in steps], rl.CFG_STEPS + ["LIST"])
        for s, ops in steps:
            self.assertIn("COND=EVEN", ops, s)

    def test_configured_libraries_listed(self):
        cmds = set(rl.listds_commands(JCL))
        for d in ("ISF.LINKLIB", "ISF.ISFCLST", "SYSGEN.NJE38.AUTHLIB", "SYS1.VTAMLIB", "SYS1.HELP",
                  "SYSC.LINKLIB", "BREXX.LINKLIB", "SYSC.PROCLIB"):
            self.assertIn(d, cmds)


class SsnTable(unittest.TestCase):
    def dump(self, body_hex):
        rows = []
        for off in range(0, len(body_hex), 64):
            chunk = body_hex[off:off + 64]
            words = " ".join(chunk[i:i + 8] for i in range(0, len(chunk), 8))
            rows.append(f"            {off // 2:06X}    {words}")
        return ("                     LISTING OF LOAD MODULE IEFJSSNT        PAGE 0001\n"
                + "\n".join(rows) + "\n ******END OF LOAD MODULE LISTING\n")

    def test_empty_table(self):
        r = rl.ssn_table(self.dump("40" * 16 + "FFFFFFFF" + "40" * 12))
        self.assertTrue(r["found"])
        self.assertEqual(r["names_before_end"], [])
        self.assertEqual(r["end_marker_offset"], 16)

    def test_names_decoded(self):
        name = "JES2".encode("cp037").hex().upper() + "UFS1".encode("cp037").hex().upper()
        r = rl.ssn_table(self.dump(name + "40404040" + "FFFFFFFF"))
        self.assertEqual(r["names_before_end"], ["JES2", "UFS1"])

    def test_absent(self):
        self.assertEqual(rl.ssn_table("no listing here"), {"found": False})


if __name__ == "__main__":
    unittest.main()

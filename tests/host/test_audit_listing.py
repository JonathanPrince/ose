"""Host tests for the OSE-011 listing driver (tests/guest/audit/run_listing.py):
LISTDS member and alias parsing (formats observed on MVS/CE 2026-11-27), user
library qualification, credentials, the IEFJSSNT decode and the collision table.
No guest, no Docker."""
import importlib.util
import unittest
from unittest import mock
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


USER = "TUSER"
DSNS = rl.listds_commands(rl.qualify_user_libraries(JCL, USER))


def full_spool(skip=(), extra_member=None, ssn="complete", catalog=True, denied=None):
    """A complete synthetic spool for the job (formats as observed on MVS/CE),
    with optional damage for the replay tests."""
    out = []
    if ssn != "absent":
        body = "40" * 16 + ("FFFFFFFF" if ssn == "complete" else "40404040") + "40" * 12
        rows = [f"            {o // 2:06X}    " + " ".join(body[o + i:o + i + 8] for i in range(0, 64, 8)).strip()
                for o in range(0, len(body), 64)]
        out += ["                     LISTING OF LOAD MODULE IEFJSSNT        PAGE 0001", *rows,
                " ******END OF LOAD MODULE LISTING"]
    for d in DSNS:
        if d in skip:
            continue
        out.append(f" LISTDS '{d}' MEMBERS")
        if d == denied:
            out.append("IKJ56225I DATA SET NOT ALLOCATED, AUTHORIZATION FAILURE")
            continue
        out += [d, "--RECFM-LRECL-BLKSIZE-DSORG", "  U     **    19069   PO", "--VOLUMES--", "  MVSRES",
                "--MEMBERS--", "  IEFBR14", "  IKJEHDS1  ALIAS(LISTD,LISTDS)"]
        if extra_member and d == "SYS1.CMDLIB":
            out.append(extra_member)
    if catalog:
        out += [" LISTCAT LEVEL(OSE) ALL", "IDC3012I ENTRY OSE. NOT FOUND+", "IDC0014I LASTCC=4",
                " LISTCAT ENTRIES('OSE') ALL", "IDC3012I ENTRY OSE NOT FOUND+", "IDC0014I LASTCC=4"]
    out.append("END")
    return "\n".join(out) + "\n"


class EvidenceGate(unittest.TestCase):
    """Review R11-G1: incomplete evidence must make the audit fail."""

    def problems(self, **damage):
        return rl.analyse(full_spool(**damage), DSNS)["evidence_problems"]

    def test_complete_spool_has_no_problems(self):
        r = rl.analyse(full_spool(), DSNS)
        self.assertEqual(r["evidence_problems"], [])
        self.assertEqual(r["catalog"], {"level": "not found", "entries": "not found"})

    def test_unparsed_member_line(self):
        p = self.problems(extra_member="  this is not a member line")
        self.assertTrue(any("SYS1.CMDLIB" in x and "unparsed" in x for x in p), p)

    def test_missing_subsystem_dump(self):
        self.assertTrue(any("IEFJSSNT" in x for x in self.problems(ssn="absent")))

    def test_truncated_subsystem_dump(self):
        self.assertTrue(any("IEFJSSNT" in x and "incomplete" in x for x in self.problems(ssn="no-end-marker")))

    def test_missing_library_section(self):
        self.assertTrue(any("SYS1.LPALIB" in x for x in self.problems(skip=("SYS1.LPALIB",))))

    def test_access_denied_library_is_not_searched(self):
        p = self.problems(denied="SYSC.LINKLIB")
        self.assertTrue(any("SYSC.LINKLIB" in x and "LISTDS failed" in x for x in p), p)

    def test_absent_library_is_evidence_not_a_gap(self):
        spool = full_spool().replace(f" LISTDS '{USER}.CLIST' MEMBERS\n{USER}.CLIST",
                                     f" LISTDS '{USER}.CLIST' MEMBERS\nIKJ58503I DATA SET {USER}.CLIST NOT IN CATALOG")
        self.assertEqual(rl.analyse(spool, DSNS)["evidence_problems"], [])

    def test_missing_catalog_result(self):
        self.assertTrue(any("catalog" in x for x in self.problems(catalog=False)))


class only_keys:
    """Set environment keys for a block and restore exactly those keys afterwards
    (review R11-G2): the previous value, or removal if the key was absent. The
    rest of the environment is never cleared or rewritten. mock.patch.dict is
    not used because it restores by clearing the whole mapping and refilling it,
    which drops keys set meanwhile by anything else in the process."""

    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        import os
        for k, v in self.values.items():
            self.saved[k] = os.environ.get(k)
            os.environ[k] = v
        return self

    def __exit__(self, *exc):
        import os
        for k, old in self.saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
        return False


HOOK = {}   # MainReplay: called from the fake Hercules while main() runs


class MainReplay(unittest.TestCase):
    """Replays a spool through main() with a fake Hercules: the driver's exit
    code must reflect the evidence gate, not only the step RCs."""

    def replay(self, spool):
        import importlib.util as iu
        import os
        import sys
        import tempfile
        import shutil
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "printers").mkdir()
        rcs = "".join(f"IEF142I OSELIST {s} - STEP WAS EXECUTED - COND CODE {c}\n"
                      for s, c in [(s, "0000") for s in rl.CFG_STEPS] + [("LIST", "0004")])
        (tmp / "printers" / "prt00e.txt").write_text(rcs + spool, encoding="latin-1")

        def real(name, path):
            s = iu.spec_from_file_location(name + "_replay", path)
            m = iu.module_from_spec(s)
            s.loader.exec_module(m)
            return m
        smoke = real("mvs_smoke", ROOT / "scripts" / "lib" / "mvs-smoke.py")
        hg = real("hello_guest", ROOT / "tests" / "guest" / "hello" / "hello_guest.py")
        hg.submit_ebcdic = lambda data, port=3506: None
        shutdown = ["$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE", "$HASP085 JES2 TERMINATION COMPLETE",
                    "IEE334I HALT     EOD SUCCESSFUL"]

        class FakeHerc:
            def __init__(self, *a):
                self.console, self.quit_fallback, self.stop_mark, self.exited_early = [], False, None, False

            def wait(self, pattern, timeout):
                return "simulated"

            def send(self, cmd):
                pass

            def stop(self):
                self.stop_mark = len(self.console)
                self.console += shutdown
                if HOOK.get("during_run"):
                    HOOK["during_run"]()
                return 0
        smoke.Herc = FakeHerc
        mod = real("run_listing", ROOT / "tests" / "guest" / "audit" / "run_listing.py")
        mod.JCL = ROOT / "jcl" / "audit" / "list-libraries.jcl"
        mod.load = lambda name, path: {"mvs_smoke": smoke, "hello_guest": hg}[name]
        argv = ["run_listing.py", "--mvsce", str(tmp), "--evidence", str(tmp / "ev")]
        with mock.patch.object(sys, "argv", argv), only_keys(GUEST_USER=USER, GUEST_PASS="SECRET1"):
            try:
                mod.main()
            except SystemExit as e:
                return e.code
        return None

    def test_complete_replay_passes(self):
        self.assertEqual(self.replay(full_spool()), 0)

    def test_replay_restores_only_its_own_environment_keys(self):
        """R11-G2: the replay restores GUEST_USER/GUEST_PASS only. A key that
        something else sets while main() runs survives, the environment is never
        cleared, and a key that existed before gets its old value back."""
        import os
        import sys
        during, outer = "OSE_TEST_SET_DURING_RUN", "OSE_TEST_OUTER"
        before_argv = list(sys.argv)
        clears = []
        original_clear = os.environ.clear
        with only_keys(**{outer: "kept", "GUEST_USER": "outer-user"}):
            HOOK["during_run"] = lambda: os.environ.__setitem__(during, "set-by-other-code")
            os.environ.clear = lambda: clears.append(1) or original_clear()
            try:
                self.replay(full_spool())
            finally:
                HOOK.clear()
                del os.environ.clear                                 # back to the class method
            self.assertEqual(clears, [], "the replay cleared the process environment")
            self.assertEqual(os.environ.get(during), "set-by-other-code")
            self.assertEqual(os.environ[outer], "kept")
            self.assertEqual(os.environ["GUEST_USER"], "outer-user")
            self.assertNotIn("GUEST_PASS", os.environ)
        os.environ.pop(during, None)
        self.assertNotIn(outer, os.environ)
        self.assertEqual(sys.argv, before_argv)

    def test_unparsed_line_fails_the_run(self):
        self.assertEqual(self.replay(full_spool(extra_member="  garbage here")), 1)

    def test_missing_subsystem_dump_fails_the_run(self):
        self.assertEqual(self.replay(full_spool(ssn="absent")), 1)


if __name__ == "__main__":
    unittest.main()

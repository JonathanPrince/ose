"""Regression tests for the OSE-003 review findings R03-1..R03-5 (2026-11-27).

Every test runs on the host with fakes: no Docker, no guest, no network.
  R03-1  sysgen-in-container.sh refuses a resumed tree that is not SYSGEN_COMMIT + P-01
  R03-2  doctor.sh fails when the in-container checks cannot run or do not finish
  R03-3  mvs-smoke.py requires the ordered shutdown messages after the shutdown request
  R03-4  mvs-smoke.py ignores handshake files from earlier runs
  R03-5  upstream/debian/packages.lock.json is valid and debpins.py checks hashes before install
The shell tests need bash and git; they are skipped (not passed) when bash is missing.
"""
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_bash():
    if os.environ.get("OSE_BASH"):
        return os.environ["OSE_BASH"]
    b = shutil.which("bash")
    if b and "system32" not in b.lower():          # not the WSL launcher on Windows
        return b
    for c in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(c).exists():
            return c
    return None


BASH = find_bash()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def posix(p: Path) -> str:
    return str(p).replace("\\", "/")


# --- R03-3 and R03-4: mvs-smoke.py ---------------------------------------------
SHUTDOWN = ["$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE",
            "IEF196I $HASP085 JES2 TERMINATION COMPLETE",
            "IEE334I HALT     EOD SUCCESSFUL"]


class FakeClock:
    def __init__(self, on_sleep=None):
        self.now, self.sleeps, self.on_sleep = 0.0, 0, on_sleep

    def time(self):
        self.now += 0.01
        return self.now

    def sleep(self, n):
        self.sleeps += 1
        self.now += n
        if self.on_sleep:
            self.on_sleep(self.sleeps)

    def strftime(self, *a):
        return "00:00:00"


def fake_herc(console_before=(), on_stop=(), exited_early=False, rc=0):
    class FakeHerc:
        def __init__(self, *a):
            self.console = list(console_before)
            self.quit_fallback = False
            self.stop_mark = None
            self.exited_early = False

        def wait(self, pattern, timeout):
            return "simulated IPL message"

        def send(self, cmd):
            pass

        def _poll(self):
            return []

        def stop(self):
            self.stop_mark = len(self.console)
            self.exited_early = exited_early
            if not exited_early:
                self.console += list(on_stop)
            return rc
    return FakeHerc


class MvsSmoke(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("mvs_smoke_under_test", ROOT / "scripts" / "lib" / "mvs-smoke.py")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_main(self, herc, *extra, clock=None):
        self.mod.Herc = herc
        if clock:
            self.mod.time = clock
        argv = sys.argv
        sys.argv = ["mvs-smoke.py", "--mvsce", str(self.tmp), "--evidence", str(self.tmp), "--tag", "t", *extra]
        try:
            self.mod.main()
        except SystemExit as e:
            return e.code
        finally:
            sys.argv = argv
        return None

    # R03-3
    def test_exit_zero_without_shutdown_messages_fails(self):
        self.assertEqual(self.run_main(fake_herc(on_stop=[])), 1)
        self.assertIn("shutdown_missing: ['$HASP099', '$HASP085', 'IEE334I']",
                      (self.tmp / "t-result.txt").read_text())

    def test_premature_exit_fails_even_with_messages(self):
        self.assertEqual(self.run_main(fake_herc(console_before=SHUTDOWN, exited_early=True)), 1)

    def test_messages_from_before_the_request_do_not_count(self):
        self.assertEqual(self.run_main(fake_herc(console_before=SHUTDOWN, on_stop=[])), 1)

    def test_out_of_order_fails(self):
        self.assertEqual(self.run_main(fake_herc(on_stop=list(reversed(SHUTDOWN)))), 1)

    def test_partial_shutdown_fails(self):
        self.assertEqual(self.run_main(fake_herc(on_stop=SHUTDOWN[:2])), 1)

    def test_nonzero_rc_fails(self):
        self.assertEqual(self.run_main(fake_herc(on_stop=SHUTDOWN, rc=1)), 1)

    def test_clean_shutdown_passes(self):
        self.assertEqual(self.run_main(fake_herc(on_stop=["noise", *SHUTDOWN])), 0)

    # R03-4
    def plant_stale(self):
        for n in ("t-ready", "t-tso-done", "t-OLD-ready", "t-OLD-tso-done"):
            (self.tmp / n).write_text("previous run\n")

    def test_stale_done_marker_is_not_trusted(self):
        self.plant_stale()
        clock = FakeClock()
        rc = self.run_main(fake_herc(on_stop=SHUTDOWN), "--hold-for-tso", "300", "--run-id", "NEW", clock=clock)
        self.assertGreater(clock.sleeps, 0, "the driver did not wait for this run's TSO smoke")
        self.assertEqual(rc, 1, "no TSO completion for this run must fail")
        self.assertFalse(any((self.tmp / n).exists() for n in ("t-tso-done", "t-OLD-tso-done", "t-OLD-ready")))

    def test_delayed_worker_for_this_run_is_waited_for(self):
        self.plant_stale()
        done = self.tmp / "t-NEW-tso-done"
        clock = FakeClock(on_sleep=lambda n: n == 20 and done.write_text("done\n"))
        rc = self.run_main(fake_herc(on_stop=SHUTDOWN), "--hold-for-tso", "300", "--run-id", "NEW", clock=clock)
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(clock.sleeps, 20)
        self.assertEqual((self.tmp / "t-NEW-ready").read_text(), "NEW\n")

    def test_hold_requires_run_id(self):
        self.assertEqual(self.run_main(fake_herc(on_stop=SHUTDOWN), "--hold-for-tso", "300"), 2)


# --- R03-2: doctor.sh -----------------------------------------------------------
FAKE_DOCKER = r"""#!/bin/sh
case "$1" in
  info) exit 0 ;;
  version) echo 27.0.0; exit 0 ;;
  image) exit 0 ;;
  run)
    case "$*" in
      *WANT_VER*) # the in-container checks
        case "$FAKE_MODE" in
          start-fails) echo "docker: Error response from daemon: simulated runtime error" >&2; exit 125 ;;
          dies-midway) echo "ok    OS Debian"; exit 0 ;;
          ok) echo "ok    OS Debian"; echo "doctor-container-checks-complete"; exit 0 ;;
        esac ;;
      *) exit 0 ;;   # the package-pin check
    esac ;;
esac
exit 0
"""


@unittest.skipUnless(BASH, "bash not found (set OSE_BASH)")
class Doctor(unittest.TestCase):
    def run_doctor(self, mode):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        d = tmp / "docker"
        d.write_text(FAKE_DOCKER, newline="\n")
        d.chmod(d.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, FAKE_MODE=mode, MIN_FREE_GB="0", PYTHON=posix(Path(sys.executable)))
        cmd = f'PATH="$(cygpath -u "{posix(tmp)}" 2>/dev/null || echo "{posix(tmp)}"):$PATH" sh "{posix(ROOT)}/scripts/doctor.sh"'
        p = subprocess.run([BASH, "-c", cmd], env=env, capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def test_container_start_failure_fails(self):
        rc, out = self.run_doctor("start-fails")
        self.assertEqual(rc, 1, out)
        self.assertIn("docker run exited 125", out)

    def test_container_dying_midway_fails(self):
        rc, out = self.run_doctor("dies-midway")
        self.assertEqual(rc, 1, out)
        self.assertIn("did not complete", out)

    def test_complete_checks_pass(self):
        rc, out = self.run_doctor("ok")
        self.assertEqual(rc, 0, out)


# --- R03-1: sysgen-in-container.sh ------------------------------------------------
@unittest.skipUnless(BASH and shutil.which("git"), "bash or git not found")
class ResumeAdmission(unittest.TestCase):
    """A resumed volume tree is admitted only if it is exactly SYSGEN_COMMIT + P-01."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "sysgen"
        self.repo.mkdir()
        g = self.git
        g("init", "-q")
        g("config", "user.email", "t@example.invalid")
        g("config", "user.name", "t")
        g("config", "core.autocrlf", "false")
        (self.repo / "mvslovers.conf").write_text("[mvp]\ncommit = main\n", newline="\n")
        (self.repo / "sysgen.py").write_text("#!/bin/sh\ntouch \"$(dirname \"$0\")/RAN\"\n", newline="\n")
        g("add", "-A")
        g("commit", "-qm", "pin")
        self.pin = g("rev-parse", "HEAD").strip()
        (self.repo / "mvslovers.conf").write_text("[mvp]\ncommit = 4c004a59\n", newline="\n")
        self.patch = self.tmp / "p01.patch"
        self.patch.write_text(g("diff"), newline="\n")
        # the state a real step 1 leaves: pin checked out, P-01 applied, untracked build products
        (self.repo / "temp").mkdir()
        (self.repo / "temp" / "product.bin").write_text("x")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.repo), *a], check=True, capture_output=True,
                              text=True).stdout

    def run_wrapper(self):
        ev = self.tmp / "evidence"
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        env = dict(os.environ, HOME=posix(home), SYSGEN_DIR=posix(self.repo), EVIDENCE_DIR=posix(ev),
                   P01=posix(self.patch), SYSGEN_COMMIT=self.pin, RAKF_COMMIT="0" * 40, MVP_COMMIT="0" * 40,
                   ATTEMPTS="1", GIT_CONFIG_NOSYSTEM="1")
        p = subprocess.run([BASH, posix(ROOT / "scripts" / "lib" / "sysgen-in-container.sh")],
                           env=env, capture_output=True, text=True)
        log = (ev / "wrapper.log").read_text() if (ev / "wrapper.log").exists() else ""
        return p.returncode, log + p.stdout + p.stderr

    def assert_refused(self, why):
        rc, out = self.run_wrapper()
        self.assertEqual(rc, 10, out)
        self.assertIn("step 1b FAILED", out)
        self.assertIn(why, out)
        self.assertNotIn("step 3:", out, "validation must stop before step 3")
        self.assertFalse((self.repo / "RAN").exists(), "sysgen.py must not run")

    def test_pin_plus_patch_is_admitted(self):
        rc, out = self.run_wrapper()
        self.assertIn("step 1b ok", out)
        # step 3 then fails here because the real pin checker (/ose/...) is absent; sysgen never runs
        self.assertFalse((self.repo / "RAN").exists())

    def test_wrong_head_is_refused(self):
        self.git("stash", "-q")
        (self.repo / "other").write_text("y")
        self.git("add", "other")
        self.git("commit", "-qm", "not the pin")
        self.git("stash", "pop", "-q")
        self.assert_refused("is not the pin")

    def test_missing_patch_is_refused(self):
        self.git("checkout", "-q", "--", "mvslovers.conf")
        self.assert_refused("are not")

    def test_changed_tracked_file_is_refused(self):
        with (self.repo / "sysgen.py").open("a", newline="\n") as f:
            f.write("echo tampered\n")
        self.assert_refused("sysgen.py")

    def test_deleted_tracked_file_is_refused(self):
        (self.repo / "sysgen.py").unlink()
        self.assert_refused("sysgen.py")


# --- R03-5: Debian package pins ---------------------------------------------------
class DebPins(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("debpins_under_test", ROOT / "scripts" / "lib" / "debpins.py")
        self.data = self.mod.load()

    def test_lock_is_valid(self):
        self.assertEqual(self.mod.check(self.data), [])

    def test_required_packages_pinned(self):
        names = {p["name"]: p for p in self.data["packages"]}
        for n in ("s3270", "netbase", "regina-rexx", "libregina3", "libregina3-dev"):
            self.assertIn(n, names)
        self.assertEqual(names["s3270"]["image"], "tools")

    def test_hash_checked_before_install(self):
        line = self.mod.install_line(self.data, "tools")
        self.assertLess(line.index("sha256sum -c -"), line.index("install -y"))
        for p in self.mod.pinned(self.data, "tools"):
            self.assertIn(p["sha256"], line)
            self.assertIn(f"{p['name']}={p['version']}", line)
        self.assertNotIn("deb.debian.org", line)

    def test_mutable_source_rejected(self):
        bad = dict(self.data, snapshot=dict(self.data["snapshot"],
                                            sources=["deb http://deb.debian.org/debian bookworm main"]))
        self.assertTrue(self.mod.check(bad))

    def test_bad_hash_rejected(self):
        pk = [dict(p) for p in self.data["packages"]]
        pk[0]["sha256"] = "abc"
        self.assertTrue(self.mod.check(dict(self.data, packages=pk)))

    def test_digest_changes_with_pins(self):
        d1 = self.mod.digest(self.data, "tools")
        pk = [dict(p) for p in self.data["packages"]]
        for p in pk:
            if p["name"] == "s3270":
                p["version"] = "9.9"
        self.assertNotEqual(d1, self.mod.digest(dict(self.data, packages=pk), "tools"))


if __name__ == "__main__":
    unittest.main()

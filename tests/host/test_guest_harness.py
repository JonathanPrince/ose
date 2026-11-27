"""Host tests for the OSE-009 guest harness (scripts/guest/guest.py and the lease
functions in scripts/lib/common.sh). Docker is a fake; no guest runs.

Covers the round-1 review findings:
  R09-1 sysgen.sh negative-pin leases its target and cleans up both leases
  R09-2 restore rolls back MVSCE *and* users.conf after a late failure (real RESTORE_SH)
  R09-3 a failing `docker ps` never counts as an idle volume
  R09-4 a script releases its lease only after its own containers are confirmed gone
  R09-5 restore --create checks the lease before any Docker change
  R09-6 no whole-environment patching: module paths are set directly
"""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_guest(tmp: Path):
    """Import guest.py and point it at private directories by setting its module
    attributes (R09-6: the process environment is not touched)."""
    spec = importlib.util.spec_from_file_location("guest_under_test", ROOT / "scripts" / "guest" / "guest.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    g.LEASEDIR, g.SNAPDIR, g.LOGDIR = tmp / "leases", tmp / "snaps", tmp / "logs"
    g._LOG = None
    return g


def dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def find_bash():
    if os.environ.get("OSE_BASH"):
        return os.environ["OSE_BASH"]
    b = shutil.which("bash")
    if b and "system32" not in b.lower():
        return b
    c = r"C:\Program Files\Git\bin\bash.exe"
    return c if Path(c).exists() else None


BASH = find_bash()
posix = lambda p: str(p).replace("\\", "/")  # noqa: E731


def shpath(p) -> str:
    """Path as the shell's own tools see it: /c/... under Git Bash, where GNU tar would
    read C:/... as host:path (observed), unchanged elsewhere."""
    if BASH and os.name == "nt":
        r = subprocess.run([BASH, "-c", f'cygpath -u "{posix(p)}"'], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return posix(p)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.g = load_guest(self.tmp)
        self.docker_calls = []
        self.running = []
        self.ps_rc = 0

        def fake_docker(*args, check=True, capture=True):
            self.docker_calls.append(args)
            if args[:2] == ("ps", "-q"):
                return subprocess.CompletedProcess(args, self.ps_rc, "\n".join(self.running),
                                                   "Cannot connect to the Docker daemon" if self.ps_rc else "")
            return subprocess.CompletedProcess(args, 0, "", "")
        self.g.docker = fake_docker

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = self.g.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def acquire(self, volume="vol-a", pid=None, task="T1"):
        args = ["lease", "acquire", "--volume", volume, "--task", task, "--owner", "tester"]
        if pid is not None:
            args += ["--holder-pid", str(pid)]
        return self.run_cli(*args)


class Leases(Base):
    def test_acquire_then_second_acquire_names_holder(self):
        rc, out, _ = self.acquire(pid=os.getpid())
        self.assertEqual(rc, 0)
        self.assertRegex(out.strip(), r"^[0-9a-f]{32}$")
        rc, _, err = self.acquire(pid=os.getpid(), task="T2")
        self.assertEqual(rc, self.g.E_HELD)
        self.assertIn("task T1 owner tester", err)
        self.assertIn(f"pid {os.getpid()}", err)

    def test_stale_lease_is_reported_not_stolen(self):
        self.assertEqual(self.acquire(pid=dead_pid())[0], 0)
        before = (self.tmp / "leases" / "vol-a.lease").read_text()
        rc, _, err = self.acquire(pid=os.getpid(), task="T2")
        self.assertEqual(rc, self.g.E_STALE)
        self.assertIn("STALE", err)
        self.assertEqual((self.tmp / "leases" / "vol-a.lease").read_text(), before, "stale lease was modified")
        self.assertIn("STALE", self.run_cli("lease", "status", "--volume", "vol-a")[1])
        self.assertEqual(self.run_cli("lease", "break", "--volume", "vol-a")[0], 0)
        self.assertEqual(self.acquire(pid=os.getpid(), task="T2")[0], 0)

    def test_break_refuses_a_live_lease(self):
        self.acquire(pid=os.getpid())
        rc, _, err = self.run_cli("lease", "break", "--volume", "vol-a")
        self.assertEqual(rc, self.g.E_HELD)
        self.assertIn("refusing", err)
        self.assertTrue((self.tmp / "leases" / "vol-a.lease").exists())

    def test_release_and_check_need_the_token(self):
        token = self.acquire(pid=os.getpid())[1].strip()
        self.assertEqual(self.run_cli("lease", "check", "--volume", "vol-a", "--token", "0" * 32)[0], self.g.E_HELD)
        self.assertEqual(self.run_cli("lease", "release", "--volume", "vol-a", "--token", "0" * 32)[0], self.g.E_HELD)
        self.assertEqual(self.run_cli("lease", "check", "--volume", "vol-a", "--token", token)[0], 0)
        self.assertEqual(self.run_cli("lease", "release", "--volume", "vol-a", "--token", token)[0], 0)
        self.assertFalse((self.tmp / "leases" / "vol-a.lease").exists())

    def test_check_fails_when_holder_died(self):
        token = self.acquire(pid=dead_pid())[1].strip()
        self.assertEqual(self.run_cli("lease", "check", "--volume", "vol-a", "--token", token)[0], self.g.E_STALE)

    def test_leases_are_per_volume(self):
        self.assertEqual(self.acquire("vol-a", pid=os.getpid())[0], 0)
        self.assertEqual(self.acquire("vol-b", pid=os.getpid())[0], 0)

    def test_running_container_without_lease_blocks_acquire(self):
        self.running = ["abc123"]
        rc, _, err = self.acquire(pid=os.getpid())
        self.assertEqual(rc, self.g.E_BUSY)
        self.assertIn("abc123", err)

    # R09-3: Docker failure is not "idle"
    def test_docker_ps_failure_blocks_acquire(self):
        self.ps_rc = 1
        rc, _, err = self.acquire(pid=os.getpid())
        self.assertEqual(rc, self.g.E_BUSY)
        self.assertIn("cannot tell whether volume vol-a is in use", err)
        self.assertFalse((self.tmp / "leases" / "vol-a.lease").exists())

    def test_docker_ps_failure_blocks_release(self):
        token = self.acquire(pid=os.getpid())[1].strip()
        self.ps_rc = 1
        self.assertEqual(self.run_cli("lease", "release", "--volume", "vol-a", "--token", token)[0], self.g.E_BUSY)
        self.assertTrue((self.tmp / "leases" / "vol-a.lease").exists())

    # R09-4 (tool side): never release while a container runs on the volume
    def test_release_refused_while_a_container_runs(self):
        token = self.acquire(pid=os.getpid())[1].strip()
        self.running = ["c1"]
        rc, _, err = self.run_cli("lease", "release", "--volume", "vol-a", "--token", token)
        self.assertEqual(rc, self.g.E_BUSY)
        self.assertIn("kept", err)
        self.assertTrue((self.tmp / "leases" / "vol-a.lease").exists())

    def test_concurrent_create_loses_cleanly(self):
        real_read = self.g.read_lease
        calls = {"n": 0}

        def racing_read(volume):
            calls["n"] += 1
            if calls["n"] == 1:
                (self.tmp / "leases").mkdir(parents=True, exist_ok=True)
                (self.tmp / "leases" / f"{volume}.lease").write_text(json.dumps(
                    {"task": "OTHER", "owner": "x", "holder_pid": os.getpid(), "host": "h", "acquired": "t"}))
                return None
            return real_read(volume)
        self.g.read_lease = racing_read
        rc, _, err = self.acquire(pid=os.getpid())
        self.assertEqual(rc, self.g.E_HELD)
        self.assertIn("taken concurrently", err)

    def test_invalid_volume_name(self):
        self.assertEqual(self.acquire("../etc")[0], self.g.E_USAGE)

    def test_pid_alive(self):
        self.assertTrue(self.g.pid_alive(os.getpid()))
        self.assertFalse(self.g.pid_alive(dead_pid()))
        self.assertFalse(self.g.pid_alive(0))

    def test_every_command_logs_to_the_log_dir(self):
        self.acquire(pid=os.getpid())
        logs = list((self.tmp / "logs").glob("*.log"))
        self.assertTrue(logs)
        self.assertIn("lease acquired vol-a", "".join(p.read_text() for p in logs))

    def test_environment_untouched(self):
        """R09-6: loading and using the module leaves os.environ exactly as it was."""
        before = dict(os.environ)
        load_guest(self.tmp)
        self.acquire(pid=os.getpid())
        self.assertEqual(dict(os.environ), before)


class Snapshots(Base):
    def make_snapshot(self, name="snap1"):
        d = self.tmp / "snaps" / name
        d.mkdir(parents=True)
        (d / "guest.tar").write_bytes(b"tar-bytes" * 100)
        (d / "files.sha256").write_text("aa  sysgen/MVSCE/x\n")
        (d / "meta.json").write_text("{}\n")
        sums = "".join(f"{hashlib.sha256((d / n).read_bytes()).hexdigest()}  {n}\n"
                       for n in ("guest.tar", "files.sha256", "meta.json"))
        (d / "SHA256SUMS").write_text(sums)
        return d

    def test_intact_snapshot_verifies(self):
        self.make_snapshot()
        self.assertEqual(self.run_cli("snapshot", "verify", "--name", "snap1")[0], 0)

    def test_corrupted_tar_is_refused(self):
        d = self.make_snapshot()
        b = bytearray((d / "guest.tar").read_bytes())
        b[10] ^= 0x01
        (d / "guest.tar").write_bytes(bytes(b))
        rc, _, err = self.run_cli("snapshot", "verify", "--name", "snap1")
        self.assertEqual(rc, self.g.E_SNAP)
        self.assertIn("corrupted", err)

    def test_missing_or_altered_manifest_entries_are_refused(self):
        d = self.make_snapshot()
        (d / "files.sha256").write_text("bb  sysgen/MVSCE/x\n")
        self.assertEqual(self.run_cli("snapshot", "verify", "--name", "snap1")[0], self.g.E_SNAP)
        d2 = self.make_snapshot("snap2")
        (d2 / "meta.json").unlink()
        self.assertEqual(self.run_cli("snapshot", "verify", "--name", "snap2")[0], self.g.E_SNAP)
        d3 = self.make_snapshot("snap3")
        (d3 / "SHA256SUMS").write_text("not a manifest\n")
        self.assertEqual(self.run_cli("snapshot", "verify", "--name", "snap3")[0], self.g.E_SNAP)

    def test_restore_refuses_corrupted_snapshot_before_touching_docker(self):
        d = self.make_snapshot()
        (d / "guest.tar").write_bytes(b"corrupt")
        token = self.acquire(pid=os.getpid())[1].strip()
        self.docker_calls.clear()
        rc, _, _ = self.run_cli("restore", "--volume", "vol-a", "--name", "snap1", "--token", token)
        self.assertEqual(rc, self.g.E_SNAP)
        self.assertEqual(self.docker_calls, [])

    # R09-5: ownership before any Docker change
    def test_restore_create_with_wrong_token_makes_no_docker_call(self):
        self.make_snapshot()
        self.acquire("vol-new", pid=os.getpid())
        self.docker_calls.clear()
        rc, _, _ = self.run_cli("restore", "--volume", "vol-new", "--name", "snap1", "--token", "0" * 32, "--create")
        self.assertEqual(rc, self.g.E_HELD)
        self.assertEqual(self.docker_calls, [], "Docker was called before the lease check")

    def test_restore_create_without_any_lease_makes_no_docker_call(self):
        self.make_snapshot()
        self.docker_calls.clear()
        rc, _, _ = self.run_cli("restore", "--volume", "vol-new", "--name", "snap1", "--token", "0" * 32, "--create")
        self.assertEqual(rc, self.g.E_HELD)
        self.assertEqual(self.docker_calls, [])

    def test_restore_refuses_a_running_guest(self):
        self.make_snapshot()
        token = self.acquire(pid=os.getpid())[1].strip()
        self.running = ["c1"]
        rc, _, _ = self.run_cli("restore", "--volume", "vol-a", "--name", "snap1", "--token", token)
        self.assertEqual(rc, self.g.E_BUSY)

    def test_restore_maps_rollback_failure_to_its_own_code(self):
        self.make_snapshot()
        token = self.acquire(pid=os.getpid())[1].strip()

        def fake_docker(*args, check=True, capture=True):
            if args[:2] == ("ps", "-q"):
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[0] == "run" and "/snap:ro" in " ".join(args):
                return subprocess.CompletedProcess(args, 8, "", "restore: ROLLBACK FAILED; manual recovery needed")
            return subprocess.CompletedProcess(args, 0, "", "")
        self.g.docker = fake_docker
        rc, _, err = self.run_cli("restore", "--volume", "vol-a", "--name", "snap1", "--token", token)
        self.assertEqual(rc, self.g.E_ROLLBACK)
        self.assertIn("rollback failed", err)

    def test_snapshot_create_refuses_existing_name(self):
        self.make_snapshot()
        token = self.acquire(pid=os.getpid())[1].strip()
        rc, _, _ = self.run_cli("snapshot", "create", "--volume", "vol-a", "--name", "snap1", "--token", token)
        self.assertEqual(rc, self.g.E_USAGE)


@unittest.skipUnless(BASH and shutil.which("tar"), "bash/tar not found")
class RestoreScript(unittest.TestCase):
    """R09-2: the real RESTORE_SH, run under bash on a scratch tree (RESTORE_WORK and
    RESTORE_SNAP replace /work and /snap). Faults come from a PATH wrapper around mv."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        spec = importlib.util.spec_from_file_location("guest_rs", ROOT / "scripts" / "guest" / "guest.py")
        g = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(g)
        (self.tmp / "restore.sh").write_text(g.RESTORE_SH, newline="\n")
        # the snapshot: new guest content
        src = self.tmp / "src"
        (src / "sysgen" / "MVSCE" / "DASD").mkdir(parents=True)
        (src / "sysgen" / "MVSCE" / "DASD" / "new.3350").write_bytes(b"NEW DASD")
        (src / "sysgen" / "users.conf").write_bytes(b"NEWUSER NEWPW\n")
        self.snap = self.tmp / "snap"
        self.snap.mkdir()
        r = self.sh(f'cd "{shpath(src)}" && tar -cf "{shpath(self.snap)}/guest.tar" sysgen && '
                    f'find sysgen -type f | LC_ALL=C sort | xargs sha256sum > "{shpath(self.snap)}/files.sha256"')
        self.assertEqual(r.returncode, 0, r.stderr)              # the fixture itself must be sound
        # the guest volume: old content
        self.work = self.tmp / "work"
        (self.work / "sysgen" / "MVSCE" / "DASD").mkdir(parents=True)
        (self.work / "sysgen" / "MVSCE" / "DASD" / "old.3350").write_bytes(b"OLD DASD")
        (self.work / "sysgen" / "users.conf").write_bytes(b"OLDUSER OLDPW\n")
        self.before = self.tree(self.work / "sysgen")

    def sh(self, cmd, env=None):
        return subprocess.run([BASH, "-c", cmd], capture_output=True, text=True, env=env)

    def tree(self, d: Path):
        return {posix(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}

    def run_restore(self, fail_mv_from=None):
        """fail_mv_from: source-path suffixes for which `mv` fails. The forward step and
        the rollback step move different sources, so each can be failed on its own."""
        env = dict(os.environ, RESTORE_WORK=shpath(self.work), RESTORE_SNAP=shpath(self.snap))
        prefix = ""
        if fail_mv_from:
            wrap = self.tmp / "wrap"
            wrap.mkdir(exist_ok=True)
            pats = " ".join(f'*"{s}") exit 1 ;;' for s in fail_mv_from)
            (wrap / "mv").write_text('#!/bin/sh\nsrc=\nfor a in "$@"; do case "$a" in -*) ;; *) src=$a; break ;; esac; done\n'
                                     'case "$src" in ' + pats + ' esac\nexec /usr/bin/mv "$@"\n', newline="\n")
            (wrap / "mv").chmod(0o755)
            prefix = f'PATH="$(cygpath -u "{posix(wrap)}" 2>/dev/null || echo "{posix(wrap)}"):$PATH" '
        p = self.sh(prefix + f'sh "{posix(self.tmp)}/restore.sh" 4242', env=env)
        return p.returncode, p.stdout + p.stderr

    def test_success_replaces_both(self):
        rc, out = self.run_restore()
        self.assertEqual(rc, 0, out)
        t = self.tree(self.work / "sysgen")
        self.assertEqual(t, {"MVSCE/DASD/new.3350": b"NEW DASD", "users.conf": b"NEWUSER NEWPW\n"})
        self.assertFalse(list(self.work.glob(".restore-*")))

    def test_checksum_mismatch_changes_nothing(self):
        (self.snap / "files.sha256").write_text("0" * 64 + "  sysgen/users.conf\n")
        rc, out = self.run_restore()
        self.assertEqual(rc, 7, out)
        self.assertEqual(self.tree(self.work / "sysgen"), self.before)

    def test_users_conf_staging_blocked_changes_nothing(self):
        (self.work / "sysgen" / "users.conf.new").mkdir()      # the reviewer's reproduction
        rc, out = self.run_restore()
        self.assertEqual(rc, 7, out)
        self.assertIn("guest unchanged", out)
        self.assertEqual(self.tree(self.work / "sysgen"), self.before)

    def test_late_users_conf_failure_rolls_back_both(self):
        rc, out = self.run_restore(fail_mv_from=["/sysgen/users.conf.new"])
        self.assertEqual(rc, 7, out)
        self.assertIn("rolled back; guest unchanged", out)
        self.assertEqual(self.tree(self.work / "sysgen"), self.before)
        self.assertFalse(list(self.work.glob(".restore-*")))

    def test_failed_rollback_is_reported_and_keeps_the_old_guest(self):
        rc, out = self.run_restore(fail_mv_from=["/sysgen/users.conf.new", "/MVSCE.previous"])
        self.assertEqual(rc, 8, out)
        self.assertIn("ROLLBACK FAILED", out)
        kept = list(self.work.glob(".restore-*"))
        self.assertTrue(kept, "the old guest was not kept")
        self.assertEqual((kept[0] / "MVSCE.previous" / "DASD" / "old.3350").read_text(), "OLD DASD")
        self.assertEqual((kept[0] / "users.conf.previous").read_text(), "OLDUSER OLDPW\n")


FAKE_DOCKER = r"""#!/bin/sh
# stateful fake docker for the shell tests; state in $FAKE_STATE
echo "$*" >> "$FAKE_STATE/log"
case "$1" in
  ps)   [ "${FAKE_PS_FAIL:-}" = 1 ] && exit 1
        [ -f "$FAKE_STATE/running" ] && cat "$FAKE_STATE/running"; exit 0 ;;
  wait) if [ -n "${FAKE_WAIT_RC:-}" ]; then exit "$FAKE_WAIT_RC"; fi
        rm -f "$FAKE_STATE/running"; echo "${FAKE_CONTAINER_RC:-0}"; exit 0 ;;
  stop|kill) [ "${FAKE_STUCK:-}" = 1 ] || rm -f "$FAKE_STATE/running"; exit 0 ;;
  logs) echo "fake console"; exit 0 ;;
  run)  case "$*" in
          "run -d "*) echo cafe01 > "$FAKE_STATE/running"; echo cafe01; exit 0 ;;
          *awk*) echo "MVSCE02 FAKEPW1"; exit 0 ;;
        esac; exit 0 ;;
esac
exit 0
"""
FAKE_GIT = r"""#!/bin/sh
case "$*" in
  *rev-parse*) echo "$FAKE_GIT_HEAD" ;;
  *clone*) for last; do :; done; mkdir -p "$last/.git" ;;
esac
exit 0
"""


@unittest.skipUnless(BASH, "bash not found")
class ShellLeases(unittest.TestCase):
    """Real guest scripts against a fake docker/git and a private lease directory."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, text in (("docker", FAKE_DOCKER), ("git", FAKE_GIT)):
            (self.bin / name).write_text(text, newline="\n")
            (self.bin / name).chmod(0o755)
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.leases = self.tmp / "leases"
        self.leases.mkdir()
        common = (ROOT / "scripts" / "lib" / "common.sh").read_text()
        self.sysgen_commit = next(l.split("=")[1].split()[0] for l in common.splitlines() if l.startswith("SYSGEN_COMMIT="))

    def run_script(self, script, *args, **env_extra):
        env = dict(os.environ, OSE_LEASE_DIR=str(self.leases), OSE_GUEST_LOG_DIR=str(self.tmp / "logs"),
                   OSE_DOCKER=json.dumps([BASH, posix(self.bin / "docker")]), FAKE_STATE=posix(self.state),
                   PYTHON=posix(Path(sys.executable)), GUEST_STOP_TRIES="2", FAKE_GIT_HEAD=self.sysgen_commit,
                   OSE011_EVIDENCE_ROOT=posix(self.tmp / "ev11"), OSE003_EVIDENCE_DIR=posix(self.tmp / "ev3"),
                   **env_extra)
        cmd = (f'PATH="$(cygpath -u "{posix(self.bin)}" 2>/dev/null || echo "{posix(self.bin)}"):$PATH" '
               f'sh "{posix(ROOT / script)}" ' + " ".join(args))
        p = subprocess.run([BASH, "-c", cmd], env=env, capture_output=True, text=True, timeout=300)
        log = (self.state / "log").read_text() if (self.state / "log").exists() else ""
        return p.returncode, p.stdout + p.stderr, log

    def plant_lease(self, volume, task="OTHER-HOLDER"):
        (self.leases / f"{volume}.lease").write_text(json.dumps(
            {"volume": volume, "task": task, "owner": "someone", "holder_pid": os.getpid(),
             "host": socket.gethostname(), "acquired": "t", "token": "f" * 32}))

    def test_smoke_refuses_a_leased_volume(self):
        self.plant_lease("fake-vol")
        rc, out, log = self.run_script("scripts/smoke.sh", "ipl1", DASD_VOLUME="fake-vol")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("OTHER-HOLDER", out)
        self.assertNotIn("run -d", log)

    # R09-4
    def test_failed_wait_stops_own_container_before_release(self):
        rc, out, log = self.run_script("scripts/audit-listing.sh", DASD_VOLUME="fake-vol", FAKE_WAIT_RC="17")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("run -d", log)
        self.assertRegex(log, r"ps -q --filter label=ose\.lease=[0-9a-f]{16}")
        self.assertIn("stop -t 30 cafe01", log)
        self.assertFalse((self.state / "running").exists(), "our container was left running")
        self.assertFalse((self.leases / "fake-vol.lease").exists(), "lease not released after a confirmed stop")
        self.assertLess(log.index("stop -t 30"), log.rindex("ps -q --filter volume=fake-vol"))

    def test_container_that_will_not_stop_keeps_the_lease(self):
        rc, out, log = self.run_script("scripts/audit-listing.sh", DASD_VOLUME="fake-vol", FAKE_WAIT_RC="17",
                                       FAKE_STUCK="1")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("lease on fake-vol KEPT", out)
        self.assertTrue((self.leases / "fake-vol.lease").exists(), "lease released while our container runs")

    def test_docker_failure_during_cleanup_keeps_the_lease(self):
        rc, out, _ = self.run_script("scripts/audit-listing.sh", DASD_VOLUME="fake-vol", FAKE_WAIT_RC="17",
                                     FAKE_STUCK="1", FAKE_PS_FAIL="")
        self.assertNotEqual(rc, 0, out)
        self.assertTrue((self.leases / "fake-vol.lease").exists())

    def test_normal_run_releases_the_lease(self):
        rc, out, log = self.run_script("scripts/audit-listing.sh", DASD_VOLUME="fake-vol", FAKE_CONTAINER_RC="0")
        # the fake listing produces no evidence, so the export check fails: what matters here is cleanup
        self.assertFalse((self.state / "running").exists())
        self.assertFalse((self.leases / "fake-vol.lease").exists(), out)

    # R09-1
    def test_negative_pin_refuses_a_leased_target(self):
        self.plant_lease("fake-vol-negpin", task="OTHER-REVIEW-HOLDER")
        rc, out, log = self.run_script("scripts/sysgen.sh", "negative-pin", DASD_VOLUME="fake-vol")
        self.assertNotEqual(rc, 0, out)
        self.assertIn("OTHER-REVIEW-HOLDER", out)
        self.assertNotIn("volume rm", log, "the leased target was removed")
        self.assertNotIn("run -d", log, "sysgen was started on the leased target")
        self.assertFalse((self.leases / "fake-vol.lease").exists(), "the source lease was left behind")
        self.assertTrue((self.leases / "fake-vol-negpin.lease").exists(), "the other holder's lease was touched")

    def test_negative_pin_leases_both_and_releases_both(self):
        rc, out, log = self.run_script("scripts/sysgen.sh", "negative-pin", DASD_VOLUME="fake-vol",
                                       FAKE_CONTAINER_RC="1")
        self.assertEqual(rc, 0, out)               # sysgen "failed" with the wrong pin: the expected result
        self.assertIn("run -d --name ose-sysgen-run-fake-vol-negpin", log)
        self.assertRegex(log, r"run -d --name ose-sysgen-run-fake-vol-negpin --user 1000:1000 --label ose\.lease=")
        self.assertLess(log.index("ps -q --filter volume=fake-vol-negpin"), log.index("volume rm"))
        self.assertEqual(list(self.leases.glob("*.lease")), [], "a lease was left behind")


if __name__ == "__main__":
    unittest.main()

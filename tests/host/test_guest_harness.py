"""Host tests for the OSE-009 guest harness (scripts/guest/guest.py): leases
(exclusive, stale detection without takeover, token-checked release), the
busy-volume check, snapshot manifest verification and corruption refusal, and
that a guest script refuses a volume leased by someone else. Docker is stubbed;
no guest runs."""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load_guest(tmp: Path):
    with mock.patch.dict(os.environ, {"OSE_LEASE_DIR": str(tmp / "leases"), "OSE_SNAPSHOT_DIR": str(tmp / "snaps"),
                                      "OSE_GUEST_LOG_DIR": str(tmp / "logs")}):
        spec = importlib.util.spec_from_file_location("guest_under_test", ROOT / "scripts" / "guest" / "guest.py")
        g = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(g)
    g._LOG = None
    return g


def dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.g = load_guest(self.tmp)
        self.docker_calls = []
        self.running = []

        def fake_docker(*args, check=True, capture=True):
            self.docker_calls.append(args)
            out = "\n".join(self.running) if args[:2] == ("ps", "-q") else ""
            return subprocess.CompletedProcess(args, 0, out, "")
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
        pid = dead_pid()
        self.assertEqual(self.acquire(pid=pid)[0], 0)
        before = (self.tmp / "leases" / "vol-a.lease").read_text()
        rc, _, err = self.acquire(pid=os.getpid(), task="T2")
        self.assertEqual(rc, self.g.E_STALE)
        self.assertIn("STALE", err)
        self.assertEqual((self.tmp / "leases" / "vol-a.lease").read_text(), before, "stale lease was modified")
        rc, out, _ = self.run_cli("lease", "status", "--volume", "vol-a")
        self.assertIn("STALE", out)
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

    def test_concurrent_create_loses_cleanly(self):
        real_read = self.g.read_lease
        calls = {"n": 0}

        def racing_read(volume):
            calls["n"] += 1
            if calls["n"] == 1:              # our check sees nothing ...
                (self.tmp / "leases").mkdir(parents=True, exist_ok=True)
                (self.tmp / "leases" / f"{volume}.lease").write_text(json.dumps(
                    {"task": "OTHER", "owner": "x", "holder_pid": os.getpid(), "host": "h", "acquired": "t"}))
                return None                  # ... and another process creates the lease right then
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
        rc, _, err = self.run_cli("restore", "--volume", "vol-a", "--name", "snap1", "--token", token)
        self.assertEqual(rc, self.g.E_SNAP)
        self.assertEqual(self.docker_calls, [], "restore touched docker with a corrupted snapshot")

    def test_restore_needs_the_lease(self):
        self.make_snapshot()
        self.acquire(pid=os.getpid())
        rc, _, err = self.run_cli("restore", "--volume", "vol-a", "--name", "snap1", "--token", "0" * 32)
        self.assertEqual(rc, self.g.E_HELD)

    def test_restore_refuses_a_running_guest(self):
        self.make_snapshot()
        token = self.acquire(pid=os.getpid())[1].strip()
        self.running = ["c1"]
        rc, _, err = self.run_cli("restore", "--volume", "vol-a", "--name", "snap1", "--token", token)
        self.assertEqual(rc, self.g.E_BUSY)

    def test_snapshot_create_refuses_existing_name(self):
        self.make_snapshot()
        token = self.acquire(pid=os.getpid())[1].strip()
        rc, _, err = self.run_cli("snapshot", "create", "--volume", "vol-a", "--name", "snap1", "--token", token)
        self.assertEqual(rc, self.g.E_USAGE)


def find_bash():
    b = shutil.which("bash")
    if b and "system32" not in b.lower():
        return b
    c = r"C:\Program Files\Git\bin\bash.exe"
    return c if Path(c).exists() else None


BASH = os.environ.get("OSE_BASH") or find_bash()


@unittest.skipUnless(BASH, "bash not found")
class ScriptsHonourLeases(unittest.TestCase):
    """A guest script must refuse a volume whose lease another live holder owns."""

    def test_smoke_refuses_a_leased_volume(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        fake = tmp / "bin" / "docker"
        fake.parent.mkdir()
        fake.write_text("#!/bin/sh\necho \"$*\" >> \"$FAKE_LOG\"\nexit 0\n", newline="\n")
        fake.chmod(0o755)
        leases = tmp / "leases"
        leases.mkdir()
        (leases / "fake-vol.lease").write_text(json.dumps(
            {"volume": "fake-vol", "task": "OTHER-TASK", "owner": "someone", "holder_pid": os.getpid(),
             "host": __import__("socket").gethostname(), "acquired": "t", "token": "f" * 32}))
        posix = lambda p: str(p).replace("\\", "/")  # noqa: E731
        env = dict(os.environ, OSE_LEASE_DIR=str(leases), OSE_GUEST_LOG_DIR=str(tmp / "logs"),
                   OSE_DOCKER=json.dumps([BASH, posix(fake)]), FAKE_LOG=posix(tmp / "docker.log"), DASD_VOLUME="fake-vol",
                   PYTHON=posix(Path(sys.executable)))
        cmd = (f'PATH="$(cygpath -u "{posix(fake.parent)}" 2>/dev/null || echo "{posix(fake.parent)}"):$PATH" '
               f'sh "{posix(ROOT)}/scripts/smoke.sh" ipl1')
        p = subprocess.run([BASH, "-c", cmd], env=env, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OTHER-TASK", p.stderr + p.stdout)
        log = (tmp / "docker.log").read_text() if (tmp / "docker.log").exists() else ""
        self.assertNotIn("run -d", log, "a guest container was started on a leased volume")
        self.assertTrue((leases / "fake-vol.lease").exists())


if __name__ == "__main__":
    unittest.main()

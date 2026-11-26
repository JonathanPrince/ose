"""OSE-013 host tests: sysgen patch P-01 and scripts/lib/pins.py.

Test IDs (cited from dependencies.lock.json pending_enforcement):
  T-PIN-001  patch applies to pinned sysgen; <= 40 changed lines
  T-PIN-002  patched git_clone: fresh clone checks out the pinned commit
  T-PIN-003  patched git_clone: stale existing clone is moved to the pinned commit
  T-PIN-004  patched git_clone: a commit that cannot be reached is refused
  T-PIN-005  patched update_manifest leaves commit-pinned entries alone
  T-PIN-006  pins.py check-clone: pass on the pin, fail (naming it) off the pin
  T-PIN-007  pins.py check-mvp-packages: LF clone passes, autocrlf=true clone fails

Tests needing the pinned upstream sources are skipped when the caches in
artifacts/cache/{sysgen,MVP} are absent (fetched by OSE-002 / `make fetch`).
"""
import ast
import importlib.util
import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "upstream/sysgen/patches/0001-pin-mvp-and-rakf-commits.patch"
LOCK = ROOT / "dependencies.lock.json"
SYSGEN_CACHE = ROOT / "artifacts/cache/sysgen"
MVP_CACHE = ROOT / "artifacts/cache/MVP"
SYSGEN_PIN = "4746195d33d9810bb9dfb0e8a3064a33efbb0559"
GIT = shutil.which("git")

_spec = importlib.util.spec_from_file_location("pins", ROOT / "scripts/lib/pins.py")
pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pins)


def git(*args, cwd=None, check=True):
    return subprocess.run([GIT, *args], cwd=cwd, check=check, capture_output=True, text=True)


def lf_checkout(src: Path, commit: str, dest: Path, autocrlf="false"):
    git("-c", f"core.autocrlf={autocrlf}", "clone", "-q", "--no-checkout", str(src), str(dest))
    git("config", "core.autocrlf", autocrlf, cwd=dest)
    git("checkout", "-q", commit, cwd=dest)


def extract_methods(path: Path, names):
    """Compile only the named methods of class `sysgen` from sysgen.py.

    sysgen.py calls main() at module level (no __main__ guard), so importing it
    would start a real sysgen run. Instead lift the methods out with ast and
    exec them in a namespace holding just the globals they use.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "sysgen")
    funcs = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert sorted(f.name for f in funcs) == sorted(names), "methods not found in patched sysgen.py"
    ns = types.SimpleNamespace()
    g = {"os": os, "subprocess": subprocess, "logging": logging, "running_folder": ""}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(path), "exec"), g)

    class Sysgen:  # unbound methods, called with a stub self
        pass
    for n in names:
        setattr(Sysgen, n, g[n])
    ns.sysgen, ns.globals = Sysgen, g
    return ns


def make_repo(path: Path) -> list[str]:
    """Source repo with two commits on main; returns [c1, c2]."""
    path.mkdir()
    git("init", "-q", "-b", "main", cwd=path)
    git("config", "user.email", "t@example.invalid", cwd=path)
    git("config", "user.name", "t", cwd=path)
    shas = []
    for i in (1, 2):
        (path / "f.txt").write_text(f"v{i}\n")
        git("add", "f.txt", cwd=path)
        git("commit", "-q", "-m", f"c{i}", cwd=path)
        shas.append(git("rev-parse", "HEAD", cwd=path).stdout.strip())
    return shas


@unittest.skipUnless(SYSGEN_CACHE.is_dir() and GIT, "needs artifacts/cache/sysgen and git")
class PatchedSysgen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.tree = cls.tmp / "sysgen"
        lf_checkout(SYSGEN_CACHE, SYSGEN_PIN, cls.tree)
        cls.check = git("apply", "--check", str(PATCH), cwd=cls.tree, check=False)
        git("apply", str(PATCH), cwd=cls.tree)
        cls.sg = extract_methods(cls.tree / "sysgen.py", ["git_clone", "git_verify_commit"])
        spec = importlib.util.spec_from_file_location("mvslovers_patched", cls.tree / "mvslovers.py")
        cls.mvslovers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mvslovers)  # library module: no side effects at import

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.src = self.work / "src"
        self.c1, self.c2 = make_repo(self.src)
        self.sg.globals["running_folder"] = str(self.work) + "/"
        self.obj = mock.Mock()
        self.obj.git_verify_commit = lambda g, t, c: self.sg.sysgen.git_verify_commit(self.obj, g, t, c)
        real = subprocess.check_output
        # `which git` yields an MSYS path on Windows Python; resolve it portably.
        self.which = mock.patch.object(subprocess, "check_output",
                                       side_effect=lambda a, *k, **kw: GIT.encode() if a == ["which", "git"] else real(a, *k, **kw))
        self.which.start()

    def tearDown(self):
        self.which.stop()
        shutil.rmtree(self.work, ignore_errors=True)

    def clone(self, **kw):
        # git_clone names the target after repo.split("/")[-1], as for a URL
        self.sg.sysgen.git_clone(self.obj, self.src.as_posix(), out_folder="out", **kw)
        return git("rev-parse", "HEAD", cwd=self.work / "out" / "src").stdout.strip()

    def test_T_PIN_001_patch_applies_and_is_small(self):
        self.assertEqual(self.check.returncode, 0, self.check.stderr)
        diff = [l for l in PATCH.read_text(encoding="utf-8").splitlines()
                if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
        self.assertLessEqual(len(diff), 40)

    def test_T_PIN_002_fresh_clone_checks_out_pin(self):
        self.assertEqual(self.clone(commit=self.c1), self.c1)  # main is at c2

    def test_T_PIN_003_stale_clone_moved_to_pin(self):
        self.assertEqual(self.clone(), self.c2)                # unpinned: as before
        self.assertEqual(self.clone(commit=self.c1), self.c1)  # existing clone path

    def test_T_PIN_004_unreachable_commit_refused(self):
        with self.assertRaises(Exception) as cm:
            self.clone(commit="0" * 40)
        self.assertIn("pins commit", str(cm.exception))
        self.clone()  # leave a clone, then the existing-clone path must refuse too
        with self.assertRaises(Exception):
            self.clone(commit="1" * 40)

    def test_T_PIN_005_update_manifest_skips_commit_pins(self):
        conf = self.work / "m.conf"
        shutil.copy(self.tree / "mvslovers.conf", conf)
        asked = []

        def opener(url):
            asked.append(url)
            raise RuntimeError("network not allowed in test")
        out = []
        changed = self.mvslovers.update_manifest(conf, ["mvp", "rakf"], opener=opener, log=out.append)
        self.assertEqual(changed, [])
        self.assertEqual(asked, [])
        self.assertTrue(any("mvp: pinned to commit" in l for l in out))
        man = self.mvslovers.load_manifest(conf)
        self.assertEqual(man["mvp"]["commit"], component("mvp")["commit"])
        self.assertEqual(man["rakf"]["commit"], component("rakf")["commit"])


def component(name):
    return pins.component(json.loads(LOCK.read_text(encoding="utf-8")), name)


@unittest.skipUnless(MVP_CACHE.is_dir() and GIT, "needs artifacts/cache/MVP and git")
class PinsHelper(unittest.TestCase):
    MVP = component("mvp")["commit"]

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def run_cli(self, *args):
        err = io.StringIO()
        with mock.patch("sys.stderr", err), mock.patch("sys.stdout", io.StringIO()):
            rc = pins.main(["pins.py", "--lock", str(LOCK), *args])
        return rc, err.getvalue()

    def test_T_PIN_006_check_clone(self):
        lf_checkout(MVP_CACHE, self.MVP, self.work / "mvp")
        self.assertEqual(self.run_cli("check-clone", "mvp", str(self.work / "mvp"))[0], 0)
        # wrong pin: the same clone checked against RAKF's commit
        rc, err = self.run_cli("check-clone", "rakf", str(self.work / "mvp"))
        self.assertEqual(rc, 1)
        self.assertIn("rakf:", err)
        self.assertEqual(self.run_cli("check-clone", "nope", str(self.work / "mvp"))[0], 2)

    def test_T_PIN_007_mvp_packages_lf_vs_crlf(self):
        lf_checkout(MVP_CACHE, self.MVP, self.work / "lf")
        rc, err = self.run_cli("check-mvp-packages", str(self.work / "lf"))
        self.assertEqual(rc, 0, err)
        lf_checkout(MVP_CACHE, self.MVP, self.work / "crlf", autocrlf="true")
        rc, err = self.run_cli("check-mvp-packages", str(self.work / "crlf"))
        self.assertEqual(rc, 1)
        self.assertIn("mvp-pkg NJE38", err)
        self.assertIn("core.autocrlf=false", err)


if __name__ == "__main__":
    unittest.main()

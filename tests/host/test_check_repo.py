"""Unit tests for scripts/check_repo.py, including negative cases."""
import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_repo", ROOT / "scripts" / "check_repo.py")
check_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_repo)


class RepoCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for rel in check_repo.REQUIRED_FILES + ["tasks/usage.jsonl", "docs/research/README.md"]:
            src = ROOT / rel
            if src.is_file():
                (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, self.tmp / rel)
        for d in ["tasks", "docs/adr", "docs/research", "docs/runbooks", "docs/architecture",
                  "docs/interfaces", "spec", "upstream"]:
            shutil.copytree(ROOT / d, self.tmp / d, dirs_exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_real_repo_passes(self):
        self.assertEqual(check_repo.run(ROOT), [])

    def test_copy_passes(self):
        self.assertEqual(check_repo.run(self.tmp), [])

    def test_missing_required_file(self):
        (self.tmp / "docs/status.md").unlink()
        self.assertTrue(any("docs/status.md" in e for e in check_repo.run(self.tmp)))

    def test_invalid_task_status(self):
        card = next((self.tmp / "tasks").glob("OSE-002-*.md"))
        text = re.sub(r"^Status:.*$", "Status: DONE", card.read_text(encoding="utf-8"),
                      count=1, flags=re.MULTILINE)
        card.write_text(text, encoding="utf-8")
        self.assertTrue(any("invalid Status 'DONE'" in e for e in check_repo.check_tasks(self.tmp)))

    def test_task_missing_section(self):
        card = next((self.tmp / "tasks").glob("OSE-002-*.md"))
        card.write_text(card.read_text(encoding="utf-8").replace("## Handoff", "## Notes"),
                        encoding="utf-8")
        self.assertTrue(any("'## Handoff'" in e for e in check_repo.check_tasks(self.tmp)))

    def test_lock_rejects_short_sha_and_missing_keys(self):
        (self.tmp / "dependencies.lock.json").write_text(json.dumps({
            "schema_version": 1,
            "components": [{"name": "ufsd", "commit": "f0a5dd98"}]}), encoding="utf-8")
        errs = check_repo.check_lock(self.tmp)
        self.assertTrue(any("40-hex" in e for e in errs))
        self.assertTrue(any("missing key 'license_spdx'" in e for e in errs))

    def test_lock_accepts_valid_entry(self):
        (self.tmp / "dependencies.lock.json").write_text(json.dumps({
            "schema_version": 1,
            "components": [{
                "name": "ufsd", "source_url": "https://github.com/mvslovers/ufsd",
                "commit": "f0a5dd988e77685e298be0fef5173497ed7c4c74", "version": "1.5.2",
                "license_spdx": "UNRESOLVED", "redistribution": "UNRESOLVED",
                "pinned_by": "test", "verified_date": "2026-11-26", "verified_by": "test",
                "artifacts": [{"url": "x", "sha256": "0" * 64}]}]}), encoding="utf-8")
        self.assertEqual(check_repo.check_lock(self.tmp), [])

    def test_lock_excluded_and_pending_validation(self):
        p = self.tmp / "dependencies.lock.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["excluded"] = [{"name": "x", "source_url": "u", "reason": "r"}]          # no evidence
        d["pending_enforcement"] = [{"component": "nope", "issue": "i", "owner": "OSE-999"}]
        p.write_text(json.dumps(d), encoding="utf-8")
        errs = check_repo.check_lock(self.tmp)
        self.assertTrue(any("excluded[0]: missing 'evidence'" in e for e in errs))
        self.assertTrue(any("unknown component 'nope'" in e for e in errs))

    def test_usage_bad_line(self):
        (self.tmp / "tasks/usage.jsonl").write_text('{"task":"OSE-001"}\nnot json\n', encoding="utf-8")
        errs = check_repo.check_usage(self.tmp)
        self.assertTrue(any("missing key 'attempt'" in e for e in errs))
        self.assertTrue(any("invalid JSON" in e for e in errs))

    def test_duplicate_adr_number(self):
        shutil.copy(self.tmp / "docs/adr/0001-repository-as-shared-memory.md",
                    self.tmp / "docs/adr/0001-duplicate.md")
        self.assertTrue(any("duplicate number" in e for e in check_repo.check_adrs(self.tmp)))

    def test_broken_link(self):
        p = self.tmp / "docs/status.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n[x](nowhere.md)\n", encoding="utf-8")
        self.assertTrue(any("nowhere.md" in e for e in check_repo.check_links(self.tmp)))


if __name__ == "__main__":
    unittest.main()

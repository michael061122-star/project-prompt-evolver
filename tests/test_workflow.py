"""Offline behavioral checks. All repositories, commits and project evidence are synthetic."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid


HELPER = Path(__file__).resolve().parents[1] / "skills/project-prompt-evolver/scripts/prompt_library.py"
SPEC = importlib.util.spec_from_file_location("prompt_library", HELPER)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
REPO, HEAD, SOURCE, PUBLISHED = "test-owner/test-library", "a" * 40, "b" * 40, "c" * 40


def document(prompt_id="report-ppt", version="1.0.0", body=None, lineage=None, **extra):
    metadata = {
        "schema_version": 1, "id": prompt_id, "title": "季度汇报 PPT", "version": version,
        "summary": "将提供的数据制作成可编辑的汇报演示文稿。", "tags": ["PPT", "汇报"],
        "inputs": [{"name": "materials", "required": True, "description": "源资料"}],
        "requires": ["可编辑演示文稿制作与渲染能力"],
        "validation": {"level": "reviewed", "note": "只检查提示词结构，未做真实项目复现。"},
        "lineage": lineage,
    }
    metadata.update(extra)
    return "---\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n---\n" + (
        body or "读取 {{materials}}，核对数据来源，制作可编辑 PPT 并渲染检查。\n")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.test_parent = Path(os.environ.get("PROMPT_EVOLVER_TEST_DIR", tempfile.gettempdir())).resolve()
        self.root = self.test_parent / ("prompt-evolver-test-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.library = self.root / "remote"
        self.library.mkdir()
        self.cfg = self.root / "config.json"
        self.draft, self.note, self.review = [self.root / v for v in ("draft.md", "change.md", "review.json")]
        self.config = {"schema_version": 1, "library": {"repository": REPO, "branch": "main", "prefix": "prompts"},
                       "publishing": {"mode": "direct", "authorized": True}, "privacy": {"deny_terms": []}}
        p.write_json(self.cfg, self.config)
        p.write_text(self.note, "增加数据口径检查。仅离线内容检查，未在真实项目复现。\n")

    def tearDown(self):
        target = self.root.resolve()
        if target.is_relative_to(self.test_parent) and target.name.startswith("prompt-evolver-test-"):
            shutil.rmtree(target)

    def prepare(self, text, current=None, run=None, note_present=False):
        p.write_text(self.draft, text)
        metadata, _ = p.parse_prompt(text)
        path = f"prompts/{metadata['id']}/prompt.md"
        change = f"prompts/{metadata['id']}/changes/{metadata['version']}.md"
        present, absent = [], [change]
        if current is None:
            absent.append(path)
        else:
            p.write_text(self.library / path, current)
            present.append(path)
        if note_present:
            p.write_text(self.library / change, "Existing version record.\n")
            present.append(change)
            absent.remove(change)
        p.snapshot(self.library, REPO, "main", HEAD, present, absent)
        p.review_template(self.draft, self.note, self.review)
        review = p.load_json(self.review)
        review.update({"completion": {"status": "user-accepted", "evidence": ["Synthetic accepted outcome."]},
                       "privacy_reviewed": True, "generalization_reviewed": True,
                       "baseline_reviewed": True, "validation_evidence": ["Offline prompt inspection."]})
        p.write_json(self.review, review)
        return lambda: p.make_plan(self.draft, self.note, self.library, HEAD, self.cfg, self.review, run)

    def baseline(self):
        base = self.root / "original.md"
        p.write_text(base, document())
        p.record_use(base, REPO, "prompts/report-ppt/prompt.md", SOURCE, self.root / "run")
        return self.root / "run/run.json", p.read_run(self.root / "run/run.json")

    def test_new_plan_limits_writes_and_preserves_other_paths(self):
        unrelated = self.library / "README.md"
        p.write_text(unrelated, "Leave this file alone.\n")
        result = self.prepare(document())()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["plan"]["files"]), 2)
        self.assertEqual(p.read_text(unrelated), "Leave this file alone.\n")
        self.assertEqual(p.verify_plan(result["plan"], self.cfg), result["plan"])

    def test_update_retains_used_baseline(self):
        run, source = self.baseline()
        updated = document(version="1.1.0", body="使用 {{materials}}；先检查统计周期、单位，再制作并渲染 PPT。\n",
                           lineage={"kind": "update", "source": source})
        plan = self.prepare(updated, document(), run)()["plan"]
        self.assertEqual(plan["kind"], "update")
        self.assertEqual(p.parse_prompt(plan["files"][0]["content"])[0]["lineage"]["source"]["commit"], SOURCE)

    def test_existing_prompt_cannot_be_updated_without_actual_source(self):
        make = self.prepare(document(version="1.1.0", body="使用 {{materials}} 并增加实际检查。"), document())
        with self.assertRaises(p.Blocked):
            make()

    def test_version_only_change_is_noop(self):
        self.assertEqual(self.prepare(document(version="9.0.0"), document())()["status"], "no-op")

    def test_variant_creates_new_id_with_source(self):
        run, source = self.baseline()
        candidate = document(prompt_id="academic-defense-ppt", lineage={"kind": "variant", "source": source},
                             body="根据 {{materials}} 构建学术论证并核对引用。")
        plan = self.prepare(candidate, run=run)()["plan"]
        self.assertEqual(plan["kind"], "variant")
        self.assertIn("academic-defense-ppt", plan["files"][0]["path"])

    def test_remote_advance_requires_three_way_integration(self):
        run, source = self.baseline()
        latest = document(version="1.1.0", body="使用 {{materials}} 并交付可编辑文件和预览。")
        candidate = document(version="1.2.0", body="使用 {{materials}}；检查单位，交付可编辑文件和预览。",
                             lineage={"kind": "update", "source": source})
        make = self.prepare(candidate, latest, run)
        with self.assertRaises(p.Blocked):
            make()
        integration = p.identity(REPO, "prompts/report-ppt/prompt.md", HEAD, latest)
        candidate = document(version="1.2.0", body="使用 {{materials}}；检查单位，交付可编辑文件和预览。",
                             lineage={"kind": "update", "source": source}, integration_base=integration)
        self.assertEqual(self.prepare(candidate, latest, run)()["status"], "ready")

    def test_changed_original_snapshot_blocks_lineage(self):
        run, _ = self.baseline()
        p.write_text(run.parent / "base.md", document(body="改动 {{materials}}。"))
        with self.assertRaises(p.Blocked):
            p.read_run(run)

    def test_missing_snapshot_path_is_not_assumed_absent(self):
        make = self.prepare(document())
        p.snapshot(self.library, REPO, "main", HEAD, [], [])
        with self.assertRaises(p.Blocked):
            make()

    def test_wrong_snapshot_commit_blocks(self):
        make = self.prepare(document())
        manifest = p.load_json(self.library / ".snapshot.json")
        manifest["commit"] = SOURCE
        p.write_json(self.library / ".snapshot.json", manifest)
        with self.assertRaises(p.Blocked):
            make()

    def test_stale_review_blocks_changed_content(self):
        make = self.prepare(document())
        p.write_text(self.draft, document(body="使用 {{materials}}；增加新的未经复查步骤。"))
        with self.assertRaises(p.Blocked):
            make()

    def test_incomplete_project_cannot_publish(self):
        make = self.prepare(document())
        review = p.load_json(self.review)
        review["completion"]["status"] = "incomplete"
        p.write_json(self.review, review)
        with self.assertRaises(p.Blocked):
            make()

    def test_common_secret_blocks_without_returning_its_value(self):
        synthetic = "ghp_" + "Z" * 36
        issues = p.findings("credential=" + synthetic)
        self.assertTrue(issues)
        self.assertNotIn(synthetic, json.dumps(issues))
        with self.assertRaises(p.Blocked):
            self.prepare(document(body="使用 {{materials}}。" + synthetic))()

    def test_change_note_and_custom_terms_are_scanned(self):
        make = self.prepare(document())
        self.config["privacy"]["deny_terms"] = ["InternalClientExample"]
        p.write_json(self.cfg, self.config)
        p.write_text(self.note, "InternalClientExample")
        with self.assertRaises(p.Blocked):
            make()

    def test_no_authorization_blocks_publication_plan(self):
        make = self.prepare(document())
        self.config["publishing"]["authorized"] = False
        p.write_json(self.cfg, self.config)
        with self.assertRaises(p.Blocked):
            make()

    def test_version_change_record_cannot_be_overwritten(self):
        with self.assertRaises(p.Blocked):
            self.prepare(document(), note_present=True)()

    def test_path_traversal_and_private_paths_block(self):
        for path in ("../outside", "/absolute", "prompts/../outside", "C:/private", ".git/config", ".prompt-evolver/run.json"):
            with self.subTest(path=path), self.assertRaises(p.Blocked):
                p.within(self.library, path)

    def test_plan_tampering_blocks(self):
        plan = self.prepare(document())()["plan"]
        plan["files"][0]["content"] += "unreviewed"
        with self.assertRaises(p.Blocked):
            p.verify_plan(plan, self.cfg)

    def test_receipt_requires_actual_matching_readback(self):
        plan = self.prepare(document())()["plan"]
        plan_path = self.root / "plan.json"
        p.write_json(plan_path, plan)
        readback = self.root / "readback"
        paths = []
        for item in plan["files"]:
            p.write_text(readback / item["path"], item["content"])
            paths.append(item["path"])
        p.snapshot(readback, REPO, "main", PUBLISHED, paths, [])
        result = p.receipt(plan_path, self.cfg, readback, PUBLISHED, "main", self.root / "receipt.json")
        self.assertEqual(result["status"], "committed")
        self.assertIn(PUBLISHED, result["prompt_url"])
        p.write_text(readback / paths[0], "Different result")
        with self.assertRaises(p.Blocked):
            p.receipt(plan_path, self.cfg, readback, PUBLISHED, "main", self.root / "receipt2.json")

    def test_pr_plan_uses_deterministic_branch_and_opened_status(self):
        self.config["publishing"]["mode"] = "pr"
        p.write_json(self.cfg, self.config)
        plan = self.prepare(document())()["plan"]
        branch = p.publication_branch(plan)
        self.assertEqual(branch, p.publication_branch(copy.deepcopy(plan)))
        p.write_json(self.root / "plan.json", plan)
        readback = self.root / "readback"
        for item in plan["files"]:
            p.write_text(readback / item["path"], item["content"])
        p.snapshot(readback, REPO, branch, PUBLISHED, [v["path"] for v in plan["files"]], [])
        result = p.receipt(self.root / "plan.json", self.cfg, readback, PUBLISHED, branch,
                           self.root / "receipt.json", f"https://github.com/{REPO}/pull/1")
        self.assertEqual(result["status"], "pr-opened")

    def test_chinese_search_uses_metadata(self):
        self.prepare(document(), document())
        self.assertEqual(p.search(self.library, "prompts", "季度 汇报")["matches"][0]["id"], "report-ppt")

    def test_relative_snapshot_directory_supports_search(self):
        self.prepare(document(), document())
        relative = os.path.relpath(self.library)
        self.assertEqual(p.search(relative, "prompts", "季度")["matches"][0]["id"], "report-ppt")

    def test_invalid_branch_does_not_write_configuration(self):
        output = self.root / "bad-config.json"
        with self.assertRaises(p.Blocked):
            p.cli(["init-config", "--repo", REPO, "--branch", "../main", "--out", str(output)])
        self.assertFalse(output.exists())

    def test_duplicate_metadata_keys_are_rejected(self):
        with self.assertRaises(p.Blocked):
            p.decode('{"id":"first","id":"second"}')

    def test_undeclared_parameter_is_rejected(self):
        with self.assertRaises(p.Blocked):
            p.parse_prompt(document(body="使用 {{missing_input}}。"))

    def test_hash_is_stable_across_newline_styles(self):
        text = document()
        self.assertEqual(p.digest(text), p.digest(text.replace("\n", "\r\n")))


if __name__ == "__main__":
    unittest.main()

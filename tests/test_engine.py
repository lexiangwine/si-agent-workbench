from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from workbench.engine import Engine, MAX_REMOTE_ATTEMPTS
from workbench.providers import Result
from workbench.storage import WorkbenchError

REPO = Path(__file__).resolve().parents[1]


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ("agents", "workflows"):
            shutil.copytree(REPO / folder, self.root / folder)
        self.engine = Engine(self.root)
        self.engine.create("p001", "delivery", "虚构客户资料。预算和现场条件未确认。")

    def text(self, sid="requirements", note="需人工确认"):
        return "\n\n".join("## " + h + "\n" + note for h in self.engine.stage("p001", sid)["sections"]) + "\n"

    def imported(self, sid="requirements"):
        self.engine.prompt("p001", sid)
        self.engine.ingest("p001", sid, self.text(sid))

    def approved(self, sid="requirements"):
        self.imported(sid)
        self.engine.approve("p001", sid, "业务负责人", "已检查范围、来源与未决事项。")

    def test_create_duplicate_preserves_existing(self):
        with self.assertRaises(WorkbenchError):
            self.engine.create("p001", "delivery", "另一份输入")
        self.assertIn("虚构", (self.engine.store.project("p001") / "brief.md").read_text())

    def test_reject_empty_or_large_brief(self):
        for value in (" ", "A" * 120001):
            with self.assertRaises(WorkbenchError):
                self.engine.create("p002", "delivery", value)

    def test_import_requires_prompt_contract(self):
        with self.assertRaises(WorkbenchError):
            self.engine.ingest("p001", "requirements", self.text())

    def test_reject_stale_prompt_import(self):
        self.engine.prompt("p001", "requirements")
        (self.engine.store.project("p001") / "brief.md").write_text("输入已经变更")
        with self.assertRaises(WorkbenchError):
            self.engine.ingest("p001", "requirements", self.text())

    def test_import_checks_required_sections(self):
        self.engine.prompt("p001", "requirements")
        with self.assertRaises(WorkbenchError):
            self.engine.ingest("p001", "requirements", "# 只有一个标题")
        self.assertEqual("not_started", self.engine.current_status("p001", "requirements"))

    def test_gate_blocks_unapproved_upstream(self):
        self.imported()
        with self.assertRaises(WorkbenchError):
            self.engine.prompt("p001", "technical")

    def test_approval_unlocks_next_and_context_carries_evidence(self):
        self.approved()
        path = self.engine.prompt("p001", "technical")
        self.assertIn("上游交付 requirements", path.read_text())
        self.assertIn("需人工确认", path.read_text())

    def test_brief_edit_invalidates_current_and_downstream(self):
        self.approved()
        self.approved("technical")
        (self.engine.store.project("p001") / "brief.md").write_text("新范围")
        status = self.engine.status("p001")
        self.assertEqual(["stale", "stale"], [x["status"] for x in status["stages"][:2]])
        with self.assertRaises(WorkbenchError):
            self.engine.approve("p001", "requirements", "负责人", "旧成果")

    def test_artifact_tamper_invalidates_approval(self):
        self.approved()
        self.engine.artifact_path("p001", "requirements").write_text(self.text(note="新内容"))
        self.assertEqual("stale", self.engine.current_status("p001", "requirements"))

    def test_reapproval_invalidates_downstream_even_identical_text(self):
        self.approved()
        self.approved("technical")
        self.approved()
        self.assertEqual("stale", self.engine.current_status("p001", "technical"))

    def test_role_prompt_edit_invalidates_approval(self):
        self.approved()
        with (self.root / "agents/analyst.md").open("a") as f:
            f.write("\n新增范围要求")
        self.assertEqual("stale", self.engine.current_status("p001", "requirements"))

    def test_demo_and_production_approvals_are_separate(self):
        value = self.engine.demo("demo")
        self.assertEqual("demo_complete", value["status"])
        self.assertTrue(all(x["status"] == "demo_approved" for x in value["stages"]))
        with self.assertRaises(WorkbenchError):
            self.engine.approve("demo", "requirements", "负责人", "试图正式审批")
        self.imported()
        with self.assertRaises(WorkbenchError):
            self.engine.approve("p001", "requirements", "demo", "模拟", demo=True)

    def test_all_stages_manual_end_to_end(self):
        for stage in self.engine.flow("p001")["stages"]:
            self.approved(stage["id"])
        self.assertEqual("complete", self.engine.status("p001")["status"])
        path = self.engine.report("p001")
        self.assertIn("审批", path.read_text())
        self.assertEqual(6, len(self.engine.store.load("p001")["stages"]))

    def test_engineering_demo(self):
        self.assertEqual(4, len(self.engine.demo("eng", "engineering")["stages"]))

    def test_run_without_explicit_flags_does_not_call_provider(self):
        with patch("workbench.providers.complete") as network:
            with self.assertRaises(WorkbenchError):
                self.engine.run("p001", "requirements", self.root / "absent", True, False)
            network.assert_not_called()

    def run_mock(self, complete):
        profile = {"api":"responses", "endpoint":"https://example.com/v1/responses", "allowed_hosts":["example.com"],
                   "api_key_env":"TEST_API_KEY", "model":"test-model", "max_output_tokens":1000, "timeout_seconds":1}
        with patch.dict("os.environ", {"TEST_API_KEY":"not-a-real-credential"}), \
                patch("workbench.providers.profile_for", return_value=("test", profile)), \
                patch("workbench.providers.complete", side_effect=complete):
            return self.engine.run("p001", "requirements", self.root / "unused", True, True)

    def test_remote_draft_is_never_autoapproved(self):
        result = self.run_mock(lambda *a: Result(self.text(), {"input_tokens":100}))
        self.assertEqual("pending_review", result["stages"][0]["status"])
        self.assertEqual(1, result["remote_attempts"])

    def test_remote_failure_counts_attempt_and_has_no_artifact(self):
        def fail(*args):
            raise WorkbenchError("超时")
        with self.assertRaises(WorkbenchError):
            self.run_mock(fail)
        self.assertEqual(1, self.engine.store.load("p001")["remote_attempts"])
        self.assertFalse(self.engine.artifact_path("p001", "requirements").exists())

    def test_remote_response_cannot_hide_changed_input(self):
        def changed(*args):
            (self.engine.store.project("p001") / "brief.md").write_text("外部编辑了需求")
            return Result(self.text(), {})
        with self.assertRaises(WorkbenchError):
            self.run_mock(changed)
        self.assertFalse(self.engine.artifact_path("p001", "requirements").exists())

    def test_attempt_limit_blocks_network(self):
        state = self.engine.store.load("p001")
        state["remote_attempts"] = MAX_REMOTE_ATTEMPTS
        self.engine.store.save("p001", state)
        with self.assertRaises(WorkbenchError):
            self.run_mock(lambda *args: self.fail("不应该调用模型"))

    def test_lock_blocks_second_writer(self):
        with self.engine.store.lock("p001"):
            with self.assertRaises(WorkbenchError):
                self.engine.prompt("p001", "requirements")
        self.engine.prompt("p001", "requirements")

    def test_path_and_symlink_rejected(self):
        for value in ("../escape", "UPPER", "a/b", "", "a" * 65):
            with self.assertRaises(WorkbenchError):
                self.engine.create(value, "delivery", "资料")
        link = self.engine.store.project("p001") / "artifacts"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(WorkbenchError):
            self.engine.artifact_path("p001", "requirements")

    def test_cli_import_approve_status_end_to_end(self):
        from workbench import cli
        output = self.root / "draft.md"
        output.write_text(self.text())
        with patch.object(cli, "ROOT", self.root), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(0, cli.main(["prompt", "p001", "requirements"]))
            self.assertEqual(0, cli.main(["import", "p001", "requirements", "--file", str(output)]))
            self.assertEqual(0, cli.main(["approve", "p001", "requirements", "--by", "负责人", "--note", "已核对"]))
            self.assertEqual(0, cli.main(["status", "p001", "--json"]))
            self.assertEqual(2, cli.main(["run", "p001", "technical"]))


if __name__ == "__main__":
    unittest.main()

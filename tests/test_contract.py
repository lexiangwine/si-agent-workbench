"""Tests for the unified task contract, schema v2 (workbench/contract.py)."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from workbench.contract import (
    CHECKS,
    INPUT_KINDS,
    acceptance_for,
    default_acceptance,
    load_contract,
    validate_contract,
)
from workbench.engine import workflow
from workbench.storage import WorkbenchError

REPO = Path(__file__).resolve().parents[1]


def v2_flow():
    return {
        "contract_version": 2,
        "name": "测试流程",
        "version": "2.0",
        "stages": [
            {"id": "first", "title": "第一阶段", "role": "analyst", "gate": "G1",
             "sections": ["结论", "证据"],
             "inputs": [{"name": "brief", "kind": "brief", "required": True}],
             "acceptance": [{"check": "required_sections"}]},
            {"id": "second", "title": "第二阶段", "role": "reviewer", "gate": "G2",
             "sections": ["审查结论"],
             "inputs": [{"name": "brief", "kind": "brief", "required": True},
                        {"name": "first", "kind": "artifact", "from_stage": "first"}],
             "acceptance": [{"check": "required_sections"},
                            {"check": "section_min_chars", "min_chars": 20},
                            {"check": "approval_chain"}]},
        ],
    }


def v1_flow():
    data = v2_flow()
    data.pop("contract_version")
    for stage in data["stages"]:
        stage.pop("inputs", None)
        stage.pop("acceptance", None)
    return data


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ("agents", "workflows"):
            shutil.copytree(REPO / folder, self.root / folder)

    def write_flow(self, name, data):
        path = self.root / "workflows" / (name + ".json")
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_repo_flows_load_as_v2(self):
        for name, stages in (("delivery", 6), ("engineering", 4)):
            data = load_contract(self.root, name)
            self.assertEqual(2, data["contract_version"])
            self.assertEqual("2.0", data["version"])
            self.assertEqual(stages, len(data["stages"]))
            for stage in data["stages"]:
                self.assertIn("inputs", stage)
                self.assertIn("acceptance", stage)
            final = data["stages"][-1]
            self.assertIn({"check": "approval_chain"}, final["acceptance"])
            self.assertTrue(all(x["check"] in CHECKS for s in data["stages"] for x in s["acceptance"]))

    def test_repo_flows_inputs_follow_upstream_order(self):
        data = load_contract(self.root, "delivery")
        stages = data["stages"]
        self.assertEqual([{"name": "brief", "kind": "brief", "required": True}],
                         stages[0]["inputs"])
        self.assertEqual(["brief", "requirements", "technical", "commercial"],
                         [x["name"] for x in stages[3]["inputs"]])
        self.assertEqual(["requirements", "technical", "commercial", "implementation"],
                         [x["from_stage"] for x in stages[4]["inputs"][1:]])

    def test_workflow_wrapper_returns_normalized_contract(self):
        data = workflow(self.root, "delivery")
        self.assertEqual(2, data["contract_version"])
        self.assertEqual(6, len(data["stages"]))

    def test_v1_flow_accepted_and_normalized(self):
        self.write_flow("custom", v1_flow())
        data = load_contract(self.root, "custom")
        self.assertEqual(1, data["contract_version"])
        self.assertEqual(2, len(data["stages"]))

    def test_v1_flow_without_name_or_version_accepted(self):
        data = v1_flow()
        data.pop("name")
        data.pop("version")
        self.write_flow("custom", data)
        self.assertEqual(1, load_contract(self.root, "custom")["contract_version"])

    def test_rejects_non_object_and_bad_versions(self):
        for bad in (["not", "a", "dict"], {"contract_version": 3, "stages": []},
                    {"contract_version": "2", "stages": []},
                    {"contract_version": True, "stages": []}):
            with self.assertRaises(WorkbenchError):
                validate_contract(self.root, bad)

    def test_rejects_bad_stage_counts(self):
        for stages in ([], [v2_flow()["stages"][0]] * 21):
            data = v2_flow()
            data["stages"] = stages
            with self.assertRaises(WorkbenchError):
                validate_contract(self.root, data)

    def test_rejects_missing_name_or_version_in_v2(self):
        for key in ("name", "version"):
            data = v2_flow()
            data[key] = "  "
            with self.assertRaises(WorkbenchError):
                validate_contract(self.root, data)

    def test_rejects_duplicate_stage_id(self):
        data = v2_flow()
        data["stages"][1]["id"] = "first"
        with self.assertRaises(WorkbenchError) as ctx:
            validate_contract(self.root, data)
        self.assertIn("first", str(ctx.exception))

    def test_rejects_bad_gate(self):
        for gate in ("g1", "G", "ABC1", "G-1", ""):
            data = v2_flow()
            data["stages"][0]["gate"] = gate
            with self.assertRaises(WorkbenchError):
                validate_contract(self.root, data)
        for gate in ("G1", "R1", "E10", "AB12"):
            data = v2_flow()
            data["stages"][0]["gate"] = gate
            validate_contract(self.root, data)

    def test_rejects_missing_role_file(self):
        data = v2_flow()
        data["stages"][0]["role"] = "ghost"
        with self.assertRaises(WorkbenchError) as ctx:
            validate_contract(self.root, data)
        self.assertIn("ghost", str(ctx.exception))

    def test_rejects_bad_role_id(self):
        data = v2_flow()
        data["stages"][0]["role"] = "Bad Role"
        with self.assertRaises(WorkbenchError):
            validate_contract(self.root, data)

    def test_rejects_bad_sections(self):
        for sections in ([], ["结论", "结论"], ["结论", ""], ["结论", 3], "结论"):
            data = v2_flow()
            data["stages"][0]["sections"] = sections
            with self.assertRaises(WorkbenchError):
                validate_contract(self.root, data)

    def test_rejects_bad_inputs(self):
        cases = (
            [{"name": "x", "kind": "nope"}],
            [{"name": "x", "kind": "artifact"}],
            [{"name": "x", "kind": "artifact", "from_stage": "missing"}],
            [{"name": "x", "kind": "artifact", "from_stage": 5}],
            [{"name": "x", "kind": "file"}],
            [{"name": "x", "kind": "file", "path": "../escape"}],
            [{"name": "x", "kind": "file", "path": "/etc/passwd"}],
            [{"name": "", "kind": "brief"}],
            [{"name": "x", "kind": "brief", "required": "yes"}],
            "not-a-list",
        )
        for inputs in cases:
            data = v2_flow()
            data["stages"][0]["inputs"] = inputs
            with self.assertRaises(WorkbenchError):
                validate_contract(self.root, data)
        data = v2_flow()
        data["stages"][0]["inputs"] = [{"name": "scope", "kind": "file", "path": "docs"}]
        validate_contract(self.root, data)

    def test_rejects_bad_acceptance(self):
        cases = (
            [{"check": "unknown_check"}],
            [{"check": "section_min_chars", "min_chars": 0}],
            [{"check": "section_min_chars", "min_chars": -1}],
            [{"check": "section_min_chars", "min_chars": "20"}],
            [{"check": "section_min_chars", "min_chars": True}],
            [{"check": "max_bytes", "max_bytes": 0}],
            ["required_sections"],
            "required_sections",
        )
        for acceptance in cases:
            data = v2_flow()
            data["stages"][0]["acceptance"] = acceptance
            with self.assertRaises(WorkbenchError):
                validate_contract(self.root, data)
        # Params are optional: defaults apply when omitted.
        data = v2_flow()
        data["stages"][0]["acceptance"] = [{"check": "section_min_chars"}, {"check": "max_bytes"}]
        validate_contract(self.root, data)

    def test_acceptance_optional_and_defaults(self):
        data = v2_flow()
        for stage in data["stages"]:
            stage.pop("acceptance", None)
        loaded = validate_contract(self.root, data)
        self.assertEqual([x["check"] for x in default_acceptance()],
                         [x["check"] for x in acceptance_for(loaded["stages"][0])])
        self.assertIn("approval_chain",
                      [x["check"] for x in acceptance_for(loaded["stages"][1], is_final=True)])
        self.assertNotIn("approval_chain",
                         [x["check"] for x in acceptance_for(loaded["stages"][0])])

    def test_default_acceptance_is_five_plus_chain(self):
        self.assertEqual(["required_sections", "section_min_chars", "no_placeholder",
                          "input_version_match", "upstream_approvals_match"],
                         [x["check"] for x in default_acceptance()])
        self.assertEqual(6, len(default_acceptance(is_final=True)))

    def test_schema_v2_document_matches_validator(self):
        schema = json.loads((REPO / "workflows" / "schema-v2.json").read_text(encoding="utf-8"))
        enum = schema["properties"]["stages"]["items"]["properties"]["acceptance"]["items"]["properties"]["check"]["enum"]
        self.assertEqual(sorted(CHECKS), sorted(enum))
        self.assertEqual(sorted(INPUT_KINDS),
                         sorted(schema["properties"]["stages"]["items"]["properties"]["inputs"]["items"]["properties"]["kind"]["enum"]))

    def test_error_names_stage_field_and_rule(self):
        data = v2_flow()
        data["stages"][1]["inputs"] = [{"name": "x", "kind": "artifact", "from_stage": "nope"}]
        with self.assertRaises(WorkbenchError) as ctx:
            validate_contract(self.root, data)
        message = str(ctx.exception)
        self.assertIn("second", message)
        self.assertIn("from_stage", message)

    def test_v1_stage_rules_still_enforced(self):
        data = v1_flow()
        data["stages"][0]["sections"] = []
        with self.assertRaises(WorkbenchError):
            validate_contract(self.root, data)


if __name__ == "__main__":
    unittest.main()

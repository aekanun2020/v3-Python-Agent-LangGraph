import json
import unittest
from pathlib import Path

from labs.lab6_todo.evidence_contract import metric_contract_by_id
from scripts.build_v2_question_inventory import sha256
from scripts.replay_v2_questions import (
    _completed_answer,
    _insufficient_specification,
    _parse_fidelity,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "evaluation" / "v2_full_question_replay.json"
THREE_QUESTION_MANIFESTS = (
    ROOT / "tests" / "evaluation" / "reconciliation_three_question_v2.json",
    ROOT / "tests" / "evaluation" / "reconciliation_three_question_v3.json",
)


class V2FullQuestionReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_inventory_is_frozen_unique_and_complete(self):
        cases = self.manifest["cases"]
        self.assertTrue(self.manifest["frozen_before_first_run"])
        self.assertEqual(self.manifest["question_count"], 63)
        self.assertEqual(len(cases), 63)
        self.assertEqual(len({item["question"] for item in cases}), 63)
        self.assertEqual(self.manifest["contract_live_count"], 38)
        self.assertEqual(self.manifest["general_agent_live_count"], 25)

    def test_manual_history_extends_without_renumbering_json_core(self):
        cases = self.manifest["cases"]
        self.assertEqual(cases[60]["id"], "v2q_061")
        self.assertEqual(cases[61]["id"], "v2q_062")
        self.assertEqual(cases[62]["id"], "v2q_063")
        self.assertEqual(cases[61]["category"], "v2_manual_history")
        self.assertEqual(cases[62]["category"], "v2_manual_history")

    def test_projection_hash_and_provenance_are_stable(self):
        projection = [
            {
                "id": item["id"],
                "question": item["question"],
                "expected_contract": item["expected_contract"],
                "evaluation_mode": item["evaluation_mode"],
            }
            for item in self.manifest["cases"]
        ]
        self.assertEqual(
            sha256(projection),
            self.manifest["question_projection_sha256"],
        )
        for item in self.manifest["cases"]:
            self.assertGreaterEqual(item["provenance_count"], 1)
            self.assertEqual(item["provenance_count"], len(item["provenance"]))
            self.assertTrue(all(source["file"] for source in item["provenance"]))

    def test_every_contract_case_names_an_installed_contract(self):
        for item in self.manifest["cases"]:
            contract_id = item["expected_contract"]
            if contract_id is None:
                self.assertEqual(item["evaluation_mode"], "general_agent_live")
                continue
            self.assertEqual(item["evaluation_mode"], "contract_live")
            self.assertIsNotNone(metric_contract_by_id(contract_id))

    def test_context_fidelity_parser(self):
        parsed = _parse_fidelity(
            "[CONTEXT FIDELITY] status=supported frames=2/2 "
            "numeric_precision=1.000 label_recall=None claim_recall=1.0"
        )
        self.assertEqual(parsed["status"], "supported")
        self.assertEqual(parsed["numeric_precision"], 1.0)
        self.assertIsNone(parsed["canonical_label_recall"])
        self.assertEqual(parsed["required_claim_recall"], 1.0)

    def test_deadline_answer_is_not_a_successful_general_replay(self):
        answer = (
            "หยุดตามขีดจำกัด runtime โดยไม่สร้างข้อสรุปเกินหลักฐาน: "
            "whole-run deadline exhausted; unresolved claims=claim_001"
        )
        self.assertFalse(_completed_answer(answer))
        self.assertTrue(_completed_answer("สรุปผลจากหลักฐานครบถ้วน"))

    def test_requirement_gate_stop_is_a_valid_terminal_outcome(self):
        self.assertTrue(_insufficient_specification(
            "[REQUIREMENT GATE] verdict=insufficient_specification "
            "declared=2 detected=1"
        ))
        self.assertFalse(_insufficient_specification(
            "[CONTEXT FIDELITY] status=insufficient_evidence"
        ))

    def test_three_question_manifests_are_frozen_and_self_consistent(self):
        for path in THREE_QUESTION_MANIFESTS:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["frozen_before_first_run"])
            self.assertEqual(manifest["question_count"], 3)
            self.assertEqual(len(manifest["cases"]), 3)
            projection = [
                {
                    "id": item["id"],
                    "question": item["question"],
                    "expected_contract": item["expected_contract"],
                    "evaluation_mode": item["evaluation_mode"],
                }
                for item in manifest["cases"]
            ]
            self.assertEqual(
                sha256(projection),
                manifest["question_projection_sha256"],
            )


if __name__ == "__main__":
    unittest.main()

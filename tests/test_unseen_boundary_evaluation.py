import unittest

from scripts.evaluate_skill_routing import evaluate_routing, load_cases


class UnseenBoundaryEvaluationTests(unittest.TestCase):
    def test_suite_has_ten_cases_per_domain_and_kind(self):
        cases = load_cases()
        counts = {}
        for item in cases:
            key = (item["domain"], item["kind"])
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(counts, {
            ("hr", "paraphrase"): 10,
            ("hr", "boundary"): 10,
            ("finance", "paraphrase"): 10,
            ("finance", "boundary"): 10,
        })

    def test_identifiers_are_unique(self):
        identifiers = [item["id"] for item in load_cases()]
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_frozen_v1_is_preserved_and_semantic_v2_fixes_grain(self):
        frozen = {item["id"]: item for item in load_cases("frozen-v1")}
        semantic = {item["id"]: item for item in load_cases("semantic-v2")}
        self.assertIn("รายฝ่าย", frozen["hr_para_004"]["question"])
        self.assertIn("ระดับทั้งองค์กร", semantic["hr_para_004"]["question"])
        self.assertIsNone(frozen["hr_boundary_005"]["expected_contract"])
        self.assertEqual(
            semantic["hr_boundary_005"]["expected_contract"],
            "staffing_decision_insufficient",
        )

    def test_semantic_v3_declares_the_contract_period(self):
        semantic_v2 = {
            item["id"]: item for item in load_cases("semantic-v2")
        }
        semantic_v3 = {
            item["id"]: item for item in load_cases("semantic-v3")
        }
        self.assertNotIn("2023", semantic_v2["hr_para_004"]["question"])
        self.assertIn("2023", semantic_v3["hr_para_004"]["question"])

    def test_routing_evaluator_is_deterministic(self):
        cases = load_cases("frozen-v1")
        first = evaluate_routing(cases, "legacy")
        second = evaluate_routing(cases, "legacy")
        first_routes = [
            (item["id"], item["actual_contract"], item["passed"])
            for item in first[0]
        ]
        second_routes = [
            (item["id"], item["actual_contract"], item["passed"])
            for item in second[0]
        ]
        self.assertEqual(first_routes, second_routes)


if __name__ == "__main__":
    unittest.main()

import unittest

from labs.lab6_todo.evidence_frame import build_evidence_frame
from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState
from labs.lab6_todo.reconciliation import (
    ReconciliationVerdict,
    build_reconciliation_request,
    needs_reconciliation,
    reconcile_frames,
    result_fingerprint,
)
from labs.lab6_todo.risk_router import observe_deterministically


def frame(evidence_id: str, query: str, result: str):
    record = EvidenceRecord.from_tool(
        evidence_id,
        "execute_query_tool",
        {"query": query},
        result,
    )
    return record, build_evidence_frame(record)


class ReconciliationTests(unittest.TestCase):
    def test_grouped_aggregate_routes_to_verification(self):
        record, primary = frame(
            "primary",
            (
                "SELECT department, COUNT(*) AS employee_count "
                "FROM employees GROUP BY department"
            ),
            "department  employee_count\nผลิต  3\nบัญชี  2",
        )
        observation = observe_deterministically("count by department", record, primary)

        self.assertTrue(needs_reconciliation(observation, primary))
        self.assertIn("aggregate-comparison", observation.risk_reasons)
        request = build_reconciliation_request(observation, primary)
        self.assertEqual(
            request.expected_fields,
            ("department", "employee_count"),
        )
        self.assertIn("same output columns", request.instruction)

    def test_independent_query_matches_regardless_of_row_order(self):
        _, primary = frame(
            "primary",
            (
                "SELECT department, COUNT(*) AS employee_count "
                "FROM employees GROUP BY department"
            ),
            "department  employee_count\nผลิต  3\nบัญชี  2",
        )
        _, verification = frame(
            "verification",
            (
                "WITH active AS (SELECT department FROM employees) "
                "SELECT department, SUM(1) AS employee_count "
                "FROM active GROUP BY department"
            ),
            "department  employee_count\nบัญชี  2\nผลิต  3",
        )

        result = reconcile_frames(primary, verification)

        self.assertEqual(result.verdict, ReconciliationVerdict.MATCH)
        self.assertTrue(result.matched)
        self.assertEqual(
            result_fingerprint(primary),
            result_fingerprint(verification),
        )

    def test_conflicting_value_is_not_accepted(self):
        _, primary = frame(
            "primary",
            "SELECT department, COUNT(*) AS n FROM employees GROUP BY department",
            "department  n\nผลิต  3",
        )
        _, verification = frame(
            "verification",
            (
                "WITH e AS (SELECT department FROM employees) "
                "SELECT department, SUM(1) AS n FROM e GROUP BY department"
            ),
            "department  n\nผลิต  4",
        )

        result = reconcile_frames(primary, verification)

        self.assertEqual(result.verdict, ReconciliationVerdict.CONFLICT)
        self.assertFalse(result.matched)

    def test_repeated_sql_is_not_independent_verification(self):
        query = "SELECT COUNT(*) AS n FROM employees"
        _, primary = frame("primary", query, "n\n25")
        _, verification = frame("verification", query, "n\n25")

        result = reconcile_frames(primary, verification)

        self.assertEqual(
            result.verdict,
            ReconciliationVerdict.INVALID_VERIFICATION,
        )

    def test_reconciliation_is_rendered_with_evidence_state(self):
        _, primary = frame(
            "primary",
            "SELECT COUNT(*) AS n FROM employees",
            "n\n25",
        )
        _, verification = frame(
            "verification",
            "SELECT SUM(1) AS n FROM employees",
            "n\n25",
        )
        result = reconcile_frames(primary, verification)
        state = EvidenceState()
        state.add_reconciliation(result)

        rendered = state.render_structured()

        self.assertIn('"observer": "reconciliation"', rendered)
        self.assertIn('"verdict": "match"', rendered)


if __name__ == "__main__":
    unittest.main()

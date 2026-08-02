import unittest
from unittest.mock import patch

from labs.lab6_todo.agent_todo import run
from labs.lab6_todo.requirement_gate import assess_requirement_completeness


class RequirementGateTests(unittest.TestCase):
    def test_rejects_declared_two_conditions_when_only_one_is_given(self):
        result = assess_requirement_completeness(
            "คัดช่วงอายุงานที่สัดส่วน Charged Off สูงกว่าค่าเฉลี่ยรวมแบบ strict "
            "และผ่านทั้งสองเงื่อนไข"
        )
        self.assertFalse(result.complete)
        self.assertEqual(result.declared_count, 2)
        self.assertEqual(result.detected_count, 1)

    def test_accepts_two_explicit_comparisons(self):
        result = assess_requirement_completeness(
            "คัดกลุ่มที่ int_rate สูงกว่าค่าเฉลี่ย และ Charged Off rate "
            "สูงกว่าค่าเฉลี่ย โดยต้องผ่านทั้งสองเงื่อนไข"
        )
        self.assertTrue(result.complete)
        self.assertGreaterEqual(result.detected_count, 2)

    def test_accepts_shared_comparison_for_two_coordinated_metrics(self):
        result = assess_requirement_completeness(
            "คัดช่วง emp_length ที่ทั้ง int_rate เฉลี่ยและสัดส่วน Charged Off "
            "สูงกว่าค่าเฉลี่ยรวม โดยต้องผ่านทั้งสองเงื่อนไข"
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.detected_count, 2)

    def test_ordinary_single_metric_question_is_unchanged(self):
        result = assess_requirement_completeness(
            "นับพนักงานทั้งหมดแยกตามแผนก"
        )
        self.assertTrue(result.complete)
        self.assertIsNone(result.declared_count)

    def test_incomplete_request_stops_before_routing_or_registry_access(self):
        class RegistryMustNotBeTouched:
            def __getattribute__(self, name):
                raise AssertionError(f"registry accessed: {name}")

        with patch(
            "labs.lab6_todo.agent_todo.route_metric_contract",
            side_effect=AssertionError("router called"),
        ):
            answer = run(
                "คัดช่วงอายุงานที่สัดส่วน Charged Off "
                "สูงกว่าค่าเฉลี่ยรวม และผ่านทั้งสองเงื่อนไข",
                RegistryMustNotBeTouched(),
                max_run_seconds=1,
            )
        self.assertIn("ระบุเงื่อนไขไม่ครบ", answer)
        self.assertIn("ระบุเงื่อนไขที่สอง", answer)


if __name__ == "__main__":
    unittest.main()

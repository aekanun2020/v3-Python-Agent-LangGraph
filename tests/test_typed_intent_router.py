import unittest

from labs.lab6_todo.contract_router import RoutingPath, route_metric_contract
from labs.lab6_todo.evidence_contract import metric_contract_by_id
from labs.lab6_todo.intent_frame import NumericRole, analyze_intent_frame


Q018 = (
    "จาก skill records ทั้งหมด จงวิเคราะห์สัดส่วนระดับ `เชี่ยวชาญ` "
    "และตรวจว่าสูงถึงเป้าหมาย 50% หรือไม่ พร้อมแยกตาม `skill_category`"
)
Q021 = (
    "จำแนกตาม emp_length แล้ว กลุ่มใดมี funded_amnt เฉลี่ยสูงสุดและต่ำสุด "
    "รายงานจำนวน int_rate เฉลี่ย และ dti เฉลี่ยของกลุ่มดังกล่าว "
    "พร้อมระบุกลุ่มต่ำสุดเมื่อไม่รวม N/A"
)
Q024 = (
    "ชั่วโมงอบรมของบริษัทกระจายตาม `training_type` อย่างไร "
    "และประเภทใดเกินนโยบาย concentration limit 50% "
    "ของชั่วโมงอบรมทั้งหมด"
)
Q039 = (
    "มีพนักงานที่ปฏิบัติงาน 25 คน แต่มี performance review ปี 2023 "
    "จำนวน 7 รายการ ก่อนเปรียบเทียบผลงานระหว่างแผนก "
    "จงคำนวณ evidence coverage และประเมินว่าผ่านเกณฑ์ขั้นต่ำ 80% หรือไม่"
)


class TypedIntentRouterTests(unittest.TestCase):
    def test_four_recovered_questions_route_without_llm(self):
        expected = {
            Q018: "expert_skill_record_share",
            Q021: "finance_employment_extrema",
            Q024: "training_hours_portfolio",
            Q039: "performance_review_coverage",
        }
        for question, contract_id in expected.items():
            with self.subTest(contract_id=contract_id):
                decision = route_metric_contract(question, semantic=False)
                self.assertEqual(decision.path, RoutingPath.LEXICAL)
                self.assertEqual(decision.contract_id, contract_id)

    def test_question_owned_operator_is_bound_without_mutating_contract(self):
        decision = route_metric_contract(Q018, semantic=False)
        self.assertEqual(
            decision.contract["parameters"]["threshold"],
            {"operator": "gte", "value": 50.0, "unit": "percent"},
        )
        static = metric_contract_by_id("expert_skill_record_share")
        self.assertEqual(static["parameters"]["threshold"]["operator"], "gt")

    def test_training_policy_keeps_strict_greater_than(self):
        decision = route_metric_contract(Q024, semantic=False)
        self.assertEqual(
            decision.contract["parameters"]["threshold"]["operator"],
            "gt",
        )
        changed_operator = Q024.replace("เกินนโยบาย", "ไม่น้อยกว่านโยบาย")
        self.assertEqual(
            route_metric_contract(changed_operator, semantic=False).path,
            RoutingPath.ABSTAIN,
        )

    def test_review_numbers_have_distinct_roles(self):
        mentions = analyze_intent_frame(Q039).numeric_mentions
        self.assertEqual(
            [(item.value, item.role) for item in mentions],
            [
                (25.0, NumericRole.INPUT_OPERAND),
                (2023.0, NumericRole.TIME_PERIOD),
                (7.0, NumericRole.INPUT_OPERAND),
                (80.0, NumericRole.THRESHOLD),
            ],
        )

    def test_input_operands_do_not_change_contract_but_policy_values_do(self):
        changed_operands = Q039.replace("25 คน", "26 คน").replace(
            "7 รายการ", "8 รายการ"
        )
        self.assertEqual(
            route_metric_contract(changed_operands, semantic=False).contract_id,
            "performance_review_coverage",
        )
        for changed_policy in (
            Q039.replace("ปี 2023", "ปี 2024"),
            Q039.replace("80%", "90%"),
        ):
            with self.subTest(question=changed_policy):
                self.assertEqual(
                    route_metric_contract(changed_policy, semantic=False).path,
                    RoutingPath.ABSTAIN,
                )

    def test_non_composite_na_exclusion_does_not_use_inclusive_contract(self):
        question = (
            "จำแนกตาม emp_length แล้ว กลุ่มใดมี funded_amnt เฉลี่ยสูงสุดและ"
            "ต่ำสุดเมื่อไม่รวม N/A"
        )
        self.assertEqual(
            route_metric_contract(question, semantic=False).path,
            RoutingPath.ABSTAIN,
        )


if __name__ == "__main__":
    unittest.main()

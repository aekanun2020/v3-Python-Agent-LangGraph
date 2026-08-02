import json
import unittest
from pathlib import Path

from labs.lab6_todo.evidence_contract import (
    contract_claims,
    metric_contract_by_id,
    select_metric_contract,
)
from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState


ROOT = Path(__file__).resolve().parents[1]


def payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class HRSkillIsolationTests(unittest.TestCase):
    def test_generic_runtime_contains_no_domain_contracts(self):
        generic = payload(
            ROOT
            / "labs"
            / "lab6_todo"
            / "executable_metric_contracts.json"
        )
        self.assertEqual(generic["contracts"], [])

    def test_hr_and_finance_contracts_are_isolated(self):
        hr = payload(
            ROOT
            / "skills"
            / "hr-analytics"
            / "references"
            / "answer_contracts.json"
        )
        finance = payload(
            ROOT
            / "skills"
            / "finance-analytics"
            / "references"
            / "answer_contracts.json"
        )
        self.assertEqual(len(hr["contracts"]), 11)
        self.assertEqual(len(finance["contracts"]), 11)
        hr_ids = {item["id"] for item in hr["contracts"]}
        finance_ids = {item["id"] for item in finance["contracts"]}
        self.assertFalse(hr_ids & finance_ids)

    def test_selector_discovers_both_skills(self):
        hr = select_metric_contract(
            "นับพนักงานที่มีสถานะปฏิบัติงานแยกตาม department"
        )
        finance = select_metric_contract(
            "พอร์ต loan_amnt และ funded_amnt รวมและค่าเฉลี่ยต่อรายการ"
        )
        self.assertEqual(
            hr["id"],
            "active_headcount_by_department",
        )
        self.assertEqual(
            finance["id"],
            "finance_portfolio_totals",
        )

    def test_total_headcount_contract_preserves_all_employee_population(self):
        question = "นับพนักงานทั้งหมดแยกตามแผนก"
        selected = select_metric_contract(question)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["id"], "total_headcount_by_department")
        evidence = EvidenceState()
        evidence.accept(EvidenceRecord.from_tool(
            "hr-total-headcount",
            "execute_query_tool",
            {"query": selected["roles"][0]["query_template"]},
            (
                "department  employee_count\n"
                "เทคโนโลยีสารสนเทศ  5\n"
                "ทรัพยากรบุคคล  4\n"
                "บริหารทั่วไป  1"
            ),
        ))
        emitted = "\n".join(contract_claims(question, evidence))
        self.assertIn("department=เทคโนโลยีสารสนเทศ; employee_count=5", emitted)
        self.assertIn("population=พนักงานทุกราย", emitted)
        self.assertIn("ไม่กรอง status", emitted)

    def test_hr_contract_declares_percentage_suffix(self):
        question = (
            "สำหรับพนักงานสถานะปฏิบัติงาน จงแสดงจำนวนพนักงานประจำ "
            "และสัญญาของแต่ละแผนก พร้อมคำนวณสัดส่วน"
        )
        selected = select_metric_contract(question)
        evidence = EvidenceState()
        evidence.accept(EvidenceRecord.from_tool(
            "hr-mix",
            "execute_query_tool",
            {"query": selected["roles"][0]["query_template"]},
            (
                "department  regular_count  contract_count  "
                "employee_count  contract_pct\n"
                "เทคโนโลยีสารสนเทศ  4  1  5  20.0\n"
                "การเงิน  3  0  3  0.0\n"
                "การตลาด  2  2  4  50.0\n"
                "ทรัพยากรบุคคล  1  3  4  75.0\n"
                "บริหารทั่วไป  1  0  1  0.0\n"
                "บัญชี  2  0  2  0.0\n"
                "ผลิต  3  0  3  0.0\n"
                "วิจัยและพัฒนา  3  0  3  0.0"
            ),
        ))
        self.assertIn(
            "contract_pct=50.0%",
            "\n".join(contract_claims(question, evidence)),
        )

    def test_semantic_half_phrase_emits_contract_bound_claims(self):
        question = "หมวดทักษะใดมีสัดส่วนระเบียนระดับเชี่ยวชาญเกินครึ่งหนึ่ง"
        contract = metric_contract_by_id("expert_skill_record_share")
        self.assertIsNotNone(contract)
        evidence = EvidenceState()
        evidence.accept(EvidenceRecord.from_tool(
            "expert-share",
            "execute_query_tool",
            {"query": contract["roles"][0]["query_template"]},
            (
                "skill_category  total_skills  expert_count\n"
                "Data  10  6\n"
                "Management  8  2\n"
                "Technical  12  7\n"
                "Soft Skill  10  4\n"
                "รวมทั้งหมด  40  19"
            ),
        ))
        claims = contract_claims(
            question,
            evidence,
            contract=contract,
        )
        self.assertTrue(claims)
        self.assertIn("50%", "\n".join(claims))


if __name__ == "__main__":
    unittest.main()

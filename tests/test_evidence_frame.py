import unittest

from labs.lab6_todo.evidence_frame import (
    build_evidence_frame,
    reconcile_answer_with_context,
)
from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState


HEADCOUNT_RESULT = """       department  employee_count
เทคโนโลยีสารสนเทศ               5
          การเงิน               3
          การตลาด               4
    ทรัพยากรบุคคล               4
     บริหารทั่วไป               1
            บัญชี               2
             ผลิต               3
    วิจัยและพัฒนา               3"""


class EvidenceFrameTests(unittest.TestCase):
    def headcount_record(self):
        return EvidenceRecord.from_tool(
            "call-headcount",
            "execute_query_tool",
            {
                "query": (
                    "SELECT department, COUNT(*) AS employee_count "
                    "FROM employees WHERE status = N'ปฏิบัติงาน' "
                    "GROUP BY department ORDER BY department"
                )
            },
            HEADCOUNT_RESULT,
        )

    def test_frame_extracts_tool_context_without_relabelling(self):
        frame = build_evidence_frame(self.headcount_record())
        self.assertTrue(frame.action_succeeded)
        self.assertEqual(frame.result_kind, "tabular")
        self.assertEqual(frame.fields, ("department", "employee_count"))
        self.assertEqual(frame.grain, "group")
        self.assertEqual(frame.group_by, ("department",))
        self.assertEqual(frame.aggregations, ("COUNT",))
        self.assertIn("status = N'ปฏิบัติงาน'", frame.filters)
        self.assertEqual(
            frame.canonical_labels,
            (
                "เทคโนโลยีสารสนเทศ",
                "การเงิน",
                "การตลาด",
                "ทรัพยากรบุคคล",
                "บริหารทั่วไป",
                "บัญชี",
                "ผลิต",
                "วิจัยและพัฒนา",
            ),
        )
        self.assertEqual(frame.row_dicts()[6]["department"], "ผลิต")
        self.assertEqual(frame.row_dicts()[6]["employee_count"], 3)

    def test_frame_classifies_error_and_does_not_claim_success(self):
        record = EvidenceRecord.from_tool(
            "call-error",
            "execute_query_tool",
            {"query": "SELECT * FROM missing"},
            '{"status": "error", "message": "Invalid object name"}',
        )
        frame = build_evidence_frame(record)
        self.assertFalse(frame.action_succeeded)
        self.assertEqual(frame.result_kind, "error")
        self.assertEqual(frame.rows, ())

    def test_reconciliation_measures_complete_numeric_and_label_fidelity(self):
        evidence = EvidenceState()
        record = self.headcount_record()
        evidence.accept(record)
        evidence.add_frame(build_evidence_frame(record))
        claims = (
            "พนักงานที่มีสถานะ `ปฏิบัติงาน` มีทั้งหมด 25 คน",
            "แผนกเทคโนโลยีสารสนเทศ มีพนักงาน 5 คน",
            "แผนกการเงิน มีพนักงาน 3 คน",
            "แผนกการตลาด มีพนักงาน 4 คน",
            "แผนกทรัพยากรบุคคล มีพนักงาน 4 คน",
            "แผนกบริหารทั่วไป มีพนักงาน 1 คน",
            "แผนกบัญชี มีพนักงาน 2 คน",
            "แผนกผลิต มีพนักงาน 3 คน",
            "แผนกวิจัยและพัฒนา มีพนักงาน 3 คน",
        )
        answer = "\n".join(claims)
        report = reconcile_answer_with_context(
            "นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก",
            answer,
            evidence,
            required_claims=claims,
        )
        self.assertEqual(report.status, "supported")
        self.assertEqual(report.numeric_precision, 1.0)
        self.assertEqual(report.canonical_label_recall, 1.0)
        self.assertEqual(report.required_claim_recall, 1.0)

    def test_reconciliation_exposes_unsupported_number_and_missing_label(self):
        evidence = EvidenceState()
        record = self.headcount_record()
        evidence.accept(record)
        evidence.add_frame(build_evidence_frame(record))
        claims = (
            "แผนกผลิต มีพนักงาน 3 คน",
            "แผนกบัญชี มีพนักงาน 2 คน",
        )
        report = reconcile_answer_with_context(
            "นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก",
            "แผนกการผลิตมี 99 คน",
            evidence,
            required_claims=claims,
        )
        self.assertEqual(report.status, "contradicted")
        self.assertEqual(report.unsupported_numbers, ("99",))
        self.assertIn("ผลิต", report.missing_labels)
        self.assertIn("บัญชี", report.missing_labels)
        self.assertEqual(report.required_claim_recall, 0.0)

    def test_reconciliation_flags_unsupported_semantic_interpretation(self):
        evidence = EvidenceState()
        record = EvidenceRecord.from_tool(
            "call-certificates",
            "execute_query_tool",
            {},
            "certificate_name  certificate_count\nCPA  1\nCFA  1",
        )
        evidence.accept(record)
        evidence.add_frame(build_evidence_frame(record))

        report = reconcile_answer_with_context(
            "แสดงจำนวนใบรับรองแยกตามชื่อ",
            "CPA 1\nCFA 1\nทุกใบมี 1 ใบ แสดงว่าทีมมีทักษะหลากหลาย",
            evidence,
        )

        self.assertEqual(report.status, "partially_supported")
        self.assertEqual(len(report.unsupported_interpretations), 1)
        self.assertIn("ทักษะหลากหลาย", report.unsupported_interpretations[0])

    def test_structured_render_includes_frame_provenance(self):
        evidence = EvidenceState()
        frame = build_evidence_frame(self.headcount_record())
        evidence.add_frame(frame)
        rendered = evidence.render_structured()
        self.assertIn('"observer": "evidence_frame"', rendered)
        self.assertIn('"evidence_id": "call-headcount"', rendered)
        self.assertIn('"canonical_labels"', rendered)


if __name__ == "__main__":
    unittest.main()

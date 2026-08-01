import unittest
import math

from labs.lab6_todo.contract_router import (
    _parse_json_object,
    RoutingPath,
    route_metric_contract,
    router_fingerprint,
    validate_semantic_proposal,
)


class ContractRouterTests(unittest.TestCase):
    def test_parser_extracts_first_complete_object_from_wrapped_output(self):
        parsed = _parse_json_object(
            'reasoning {not json}\n```json\n{"contract_id": null}\n```'
        )
        self.assertIsNone(parsed["contract_id"])

    def test_fingerprint_versions_python_admission_gate(self):
        fingerprint = router_fingerprint()
        self.assertEqual(
            fingerprint["gate_version"],
            "skill-grounded-admission-gate-v1",
        )
        self.assertRegex(fingerprint["gate_source_sha256"], r"^[0-9a-f]{64}$")

    def test_lexical_fast_path_does_not_call_semantic_resolver(self):
        calls = []

        def resolver(_question, _catalog):
            calls.append(True)
            raise AssertionError("semantic resolver must not be called")

        decision = route_metric_contract(
            "สรุปพอร์ตทั้งหมดทั้งยอดรวมและค่าเฉลี่ยของ loan_amnt กับ funded_amnt",
            resolver=resolver,
            on_semantic_call=lambda: calls.append("budget"),
        )
        self.assertEqual(decision.path, RoutingPath.LEXICAL)
        self.assertEqual(decision.contract_id, "finance_portfolio_totals")
        self.assertEqual(calls, [])

    def test_canonical_thai_headcount_question_uses_grounded_semantics(self):
        question = "นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก"

        def resolver(_question, _catalog):
            return {
                "contract_id": "active_headcount_by_department",
                "confidence": 0.99,
                "reason": "active headcount at department grain",
                "term_evidence": {
                    "ปฏิบัติงาน": "ยังปฏิบัติงาน",
                    "department": "แผนก",
                    "แยกตาม": "แยกตาม",
                },
            }

        decision = route_metric_contract(question, resolver=resolver)
        self.assertEqual(decision.path, RoutingPath.SEMANTIC)
        self.assertEqual(
            decision.contract_id,
            "active_headcount_by_department",
        )

    def test_semantic_candidate_requires_grounded_spans(self):
        question = "หมวดทักษะใดมีสัดส่วนระเบียนระดับเชี่ยวชาญเกินครึ่งหนึ่ง"
        proposal = {
            "contract_id": "expert_skill_record_share",
            "confidence": 0.95,
            "reason": "same metric and threshold",
            "term_evidence": {
                "เชี่ยวชาญ": "ระดับเชี่ยวชาญ",
                "skill_category": "หมวดทักษะ",
                "50%": "เกินครึ่งหนึ่ง"
            },
        }
        decision = validate_semantic_proposal(question, proposal)
        self.assertEqual(decision.path, RoutingPath.SEMANTIC)
        self.assertEqual(decision.contract_id, "expert_skill_record_share")

        proposal["term_evidence"]["skill_category"] = "ข้อความที่ไม่มีจริง"
        rejected = validate_semantic_proposal(question, proposal)
        self.assertEqual(rejected.path, RoutingPath.ABSTAIN)

    def test_saved_semantic_v3_proposals_replay_through_current_gate(self):
        fixtures = (
            (
                "หมวดทักษะใดมีสัดส่วนระเบียนระดับเชี่ยวชาญเกินครึ่งหนึ่ง",
                "expert_skill_record_share",
                {
                    "เชี่ยวชาญ": "ระดับเชี่ยวชาญ",
                    "skill_category": "หมวดทักษะ",
                    "สัดส่วน": "เกินครึ่งหนึ่ง",
                },
            ),
            (
                "เปรียบเทียบ project value ต่อกำลังคนที่ยังทำงานอยู่รายฝ่าย "
                "แต่อย่าตีความเป็นผลิตภาพ",
                "project_value_per_active_employee",
                {
                    "project value numerator": "project value ต่อกำลังคนที่ยังทำงานอยู่รายฝ่าย",
                    "active workforce denominator": "กำลังคนที่ยังทำงานอยู่",
                    "department grain": "รายฝ่าย",
                    "do not interpret the ratio as productivity or efficiency": "แต่อย่าตีความเป็นผลิตภาพ",
                },
            ),
            (
                "จากจำนวนกำลังคนกับมูลค่างาน ช่วยบอกว่าฝ่ายไหนควรรับเพิ่มหรือลดอัตรากำลัง",
                "staffing_decision_insufficient",
                {
                    "staffing increase-or-reduction decision": "ควรรับเพิ่มหรือลดอัตรากำลัง",
                    "headcount or project-value proxy used as the decision basis": "จากจำนวนกำลังคนกับมูลค่างาน",
                },
            ),
            (
                "ช่วงอายุงานใดได้ยอดจัดสรรเฉลี่ยมากที่สุดและน้อยที่สุด โดยแสดงค่าที่ไม่ระบุด้วย",
                "finance_employment_extrema",
                {
                    "emp_length": "ช่วงอายุงานใดได้ยอดจัดสรรเฉลี่ยมากที่สุดและน้อยที่สุด",
                    "funded_amnt": "ยอดจัดสรรเฉลี่ย",
                    "สูงสุด": "มากที่สุด",
                    "ต่ำสุด": "น้อยที่สุด",
                    "N/A": "โดยแสดงค่าที่ไม่ระบุด้วย",
                },
            ),
            (
                "แบ่งภาระหนี้ต่อรายได้เป็นต่ำกว่า 10, 10 ถึงต่ำกว่า 20, "
                "20 ถึงต่ำกว่า 30, ตั้งแต่ 30 และข้อมูลว่าง",
                "finance_dti_buckets",
                {
                    "dti": "ภาระหนี้ต่อรายได้",
                    "<10": "ต่ำกว่า 10",
                    "10-<20": "10 ถึงต่ำกว่า 20",
                    "20-<30": "20 ถึงต่ำกว่า 30",
                    "30+": "ตั้งแต่ 30",
                    "NULL": "และข้อมูลว่าง",
                    "bucket": "แบ่ง",
                },
            ),
            (
                "เฉพาะ Individual แบ่ง annual_inc เป็นช่วงคงที่ต่ำกว่า 50000, "
                "50000 ถึงต่ำกว่า 70000, 70000 ถึงต่ำกว่า 100000 และตั้งแต่ 100000 ขึ้นไป",
                "finance_fixed_income_bands",
                {
                    "Individual application population": "เฉพาะ Individual",
                    "annual income field": "annual_inc",
                    "four fixed income bands": "ต่ำกว่า 50000, 50000 ถึงต่ำกว่า 70000, 70000 ถึงต่ำกว่า 100000 และตั้งแต่ 100000 ขึ้นไป",
                },
            ),
            (
                "แต่ละปี 2016-2019 จงหาส่วนต่างยอดที่ขอกับยอดที่จัดสรรและอัตราส่วนการจัดสรร",
                "finance_funding_gap_by_year",
                {
                    "year grain covering 2016 through 2019": "แต่ละปี 2016-2019",
                    "difference between requested and funded amounts": "ส่วนต่างยอดที่ขอกับยอดที่จัดสรร",
                    "funding ratio": "อัตราส่วนการจัดสรร",
                },
            ),
            (
                "คัดช่วง emp_length ที่ทั้ง int_rate เฉลี่ยและสัดส่วน Charged Off "
                "สูงกว่าค่าเฉลี่ยรวมแบบ strict โดยต้องผ่านทั้งสองเงื่อนไข",
                "finance_dual_risk_screen",
                {
                    "emp_length": "emp_length",
                    "int_rate": "int_rate",
                    "Charged Off": "Charged Off",
                    "สูงกว่าค่าเฉลี่ยทั้งพอร์ต": "สูงกว่าค่าเฉลี่ยรวมแบบ strict",
                    "strict": "strict",
                },
            ),
        )
        for question, contract_id, term_evidence in fixtures:
            with self.subTest(contract_id=contract_id):
                decision = validate_semantic_proposal(question, {
                    "contract_id": contract_id,
                    "confidence": 0.99,
                    "reason": "recorded semantic-v3 proposal",
                    "term_evidence": term_evidence,
                })
                self.assertEqual(decision.path, RoutingPath.SEMANTIC)
                self.assertEqual(decision.contract_id, contract_id)

    def test_common_thai_aliases_are_skill_grounded_for_every_core_intent(self):
        fixtures = (
            (
                "ในแต่ละฝ่าย คนที่ยังทำงานอยู่มีพนักงานถาวรกับชั่วคราวเป็นเปอร์เซ็นต์เท่าไร",
                "active_employment_mix_by_department",
                {
                    "ปฏิบัติงาน": "ยังทำงานอยู่",
                    "ประจำ": "พนักงานถาวร",
                    "สัญญา": "ชั่วคราว",
                    "แผนก": "แต่ละฝ่าย",
                    "สัดส่วน": "เป็นเปอร์เซ็นต์",
                },
            ),
            (
                "ฝ่ายไหนพึ่งพาพนักงานชั่วคราวเกินครึ่งของกำลังคนที่ยังทำงานอยู่",
                "strict_contract_dependency_policy",
                {
                    "contract dependency": "พึ่งพาพนักงานชั่วคราว",
                    "มากกว่า 50%": "เกินครึ่ง",
                    "ปฏิบัติงาน": "ยังทำงานอยู่",
                    "แผนกใด": "ฝ่ายไหน",
                },
            ),
            (
                "ตรวจความครอบคลุมของการประเมินผลงานปี 2023 สำหรับคนยังทำงานอยู่ทั้งองค์กรเทียบเป้า 80%",
                "performance_review_coverage",
                {
                    "performance review": "การประเมินผลงาน",
                    "coverage": "ความครอบคลุม",
                    "เกณฑ์": "เทียบเป้า",
                },
            ),
            (
                "ประเภทการอบรมใดมีการกระจุกตัวของชั่วโมงเกินครึ่ง",
                "training_hours_portfolio",
                {
                    "training_type": "ประเภทการอบรม",
                    "50%": "เกินครึ่ง",
                    "concentration": "การกระจุกตัวของชั่วโมง",
                },
            ),
            (
                "ประเภทใบสมัครแบบเดี่ยวกับแบบร่วมคิดเป็นร้อยละของพอร์ตเท่าไร",
                "finance_application_mix",
                {
                    "application_type": "ประเภทใบสมัคร",
                    "Individual": "แบบเดี่ยว",
                    "Joint App": "แบบร่วม",
                    "ร้อยละ": "ร้อยละของพอร์ต",
                },
            ),
            (
                "วงเงินที่ได้รับกับดอกเบี้ยรายปี 2016-2019",
                "finance_year_cohorts",
                {
                    "funded_amnt": "วงเงินที่ได้รับ",
                    "int_rate": "ดอกเบี้ย",
                    "2016": "2016",
                    "2019": "2019",
                    "รายปี": "รายปี",
                },
            ),
            (
                "แยกทุกประเภทการอยู่อาศัยแล้วเทียบวงเงินที่ได้รับ ดอกเบี้ย และภาระหนี้ต่อรายได้",
                "finance_home_ownership_segments",
                {
                    "home_ownership": "ประเภทการอยู่อาศัย",
                    "funded_amnt": "วงเงินที่ได้รับ",
                    "int_rate": "ดอกเบี้ย",
                    "dti": "ภาระหนี้ต่อรายได้",
                    "จำแนก": "แยกทุกประเภท",
                },
            ),
        )
        for question, contract_id, term_evidence in fixtures:
            with self.subTest(contract_id=contract_id):
                decision = validate_semantic_proposal(question, {
                    "contract_id": contract_id,
                    "confidence": 0.99,
                    "reason": "common Thai business alias",
                    "term_evidence": term_evidence,
                })
                self.assertEqual(decision.path, RoutingPath.SEMANTIC)
                self.assertEqual(decision.contract_id, contract_id)

    def test_skill_owned_high_precision_alias_uses_lexical_path(self):
        decision = route_metric_contract(
            "โครงการสองรายการที่มี project_value สูงสุด"
            "กินสัดส่วนมูลค่ารวมเกิน 60% หรือไม่",
            semantic=False,
        )
        self.assertEqual(decision.path, RoutingPath.LEXICAL)
        self.assertEqual(
            decision.contract_id,
            "top_two_project_concentration",
        )

    def test_natural_thai_project_value_order_passes_semantic_gate(self):
        question = (
            "โครงการสองรายการที่มีมูลค่าสูงสุดคิดเป็น "
            "concentration risk เกิน 60%"
        )
        decision = validate_semantic_proposal(question, {
            "contract_id": "top_two_project_concentration",
            "confidence": 0.99,
            "reason": "project value concentration",
            "term_evidence": {
                "project value portfolio": "โครงการสองรายการที่มีมูลค่า",
                "concentration risk": "concentration risk",
                "60%": "เกิน 60%",
                "สองอันดับ": "สองรายการ",
            },
        })
        self.assertEqual(decision.path, RoutingPath.SEMANTIC)

    def test_skill_owned_semantic_concepts_replace_literal_keywords(self):
        question = (
            "เปรียบเทียบ project value ต่อกำลังคนที่ยังทำงานอยู่รายฝ่าย "
            "แต่อย่าตีความเป็นผลิตภาพ"
        )
        proposal = {
            "contract_id": "project_value_per_active_employee",
            "confidence": 0.95,
            "reason": "same numerator, denominator, grain, and boundary",
            "term_evidence": {
                "project value numerator": "project value",
                "active workforce denominator": "กำลังคนที่ยังทำงานอยู่",
                "do not interpret the ratio as productivity or efficiency": "อย่าตีความเป็นผลิตภาพ",
                "department grain": "รายฝ่าย",
            },
        }
        decision = validate_semantic_proposal(question, proposal)
        self.assertEqual(decision.path, RoutingPath.SEMANTIC)
        self.assertEqual(
            decision.contract_id,
            "project_value_per_active_employee",
        )

    def test_skill_owned_grain_and_metric_anchors_fail_closed(self):
        department_grain = route_metric_contract(
            "ตรวจ performance review coverage รายฝ่ายเทียบเกณฑ์ 80%",
            semantic=False,
        )
        self.assertEqual(department_grain.path, RoutingPath.ABSTAIN)

        missing_interest_metric = {
            "contract_id": "finance_dual_risk_screen",
            "confidence": 0.99,
            "reason": "charged-off threshold only",
            "term_evidence": {
                "emp_length": "ช่วงอายุงาน",
                "Charged Off": "Charged Off",
                "สูงกว่าค่าเฉลี่ยทั้งพอร์ต": "สูงกว่าค่าเฉลี่ยรวม",
                "strict": "strict",
            },
        }
        question = (
            "คัดช่วงอายุงานที่สัดส่วน Charged Off "
            "สูงกว่าค่าเฉลี่ยรวมแบบ strict"
        )
        rejected = validate_semantic_proposal(
            question,
            missing_interest_metric,
        )
        self.assertEqual(rejected.path, RoutingPath.ABSTAIN)
        self.assertIn("anchors", rejected.reason)

    def test_required_domain_and_metric_identity_cannot_be_substituted(self):
        top_product = validate_semantic_proposal(
            "รายการสินค้าสองอันดับสูงสุดมี concentration risk เกิน 60%",
            {
                "contract_id": "top_two_project_concentration",
                "confidence": 0.99,
                "reason": "wrong entity",
                "term_evidence": {
                    "project value portfolio": "รายการสินค้า",
                    "concentration risk": "concentration risk",
                    "60%": "เกิน 60%",
                    "สองอันดับ": "สองอันดับ",
                },
            },
        )
        self.assertEqual(top_product.path, RoutingPath.ABSTAIN)

        dual_without_interest = validate_semantic_proposal(
            "คัดช่วง emp_length ที่ดอกเบี้ยและ Charged Off "
            "สูงกว่าค่าเฉลี่ยรวมแบบ strict แต่ไม่เอา int_rate",
            {
                "contract_id": "finance_dual_risk_screen",
                "confidence": 0.99,
                "reason": "negated required metric",
                "term_evidence": {
                    "emp_length": "emp_length",
                    "int_rate": "ดอกเบี้ย",
                    "Charged Off": "Charged Off",
                    "สูงกว่าค่าเฉลี่ยทั้งพอร์ต": "สูงกว่าค่าเฉลี่ยรวม",
                    "strict": "strict",
                },
            },
        )
        self.assertEqual(dual_without_interest.path, RoutingPath.ABSTAIN)

        for question in (
            "นับจำนวนเครื่องจักรที่ปฏิบัติงานแยกตาม department",
            "ระบบที่ปฏิบัติงานแบบประจำและสัญญาแยกตามแผนกพร้อมสัดส่วน",
        ):
            with self.subTest(question=question):
                decision = route_metric_contract(question, semantic=False)
                self.assertEqual(decision.path, RoutingPath.ABSTAIN)

    def test_semantic_call_hook_runs_once_only_on_fallback(self):
        calls = []

        def resolver(_question, _catalog):
            return {"contract_id": None, "reason": "no match"}

        decision = route_metric_contract(
            "คำถามทั่วไปที่ไม่ตรง contract",
            resolver=resolver,
            on_semantic_call=lambda: calls.append("router"),
        )
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertEqual(calls, ["router"])

    def test_headcount_only_staffing_decision_routes_to_safe_refusal(self):
        question = "ควรลดคนหรือเพิ่มคนจาก headcount เพียงอย่างเดียวหรือไม่"
        proposal = {
            "contract_id": "staffing_decision_insufficient",
            "confidence": 0.99,
            "reason": "staffing decision",
            "term_evidence": {
                "staffing increase-or-reduction decision": "ลดคนหรือเพิ่มคน",
                "headcount or project-value proxy used as the decision basis": "headcount"
            },
        }
        decision = validate_semantic_proposal(question, proposal)
        self.assertEqual(decision.path, RoutingPath.SEMANTIC)
        self.assertEqual(
            decision.contract_id,
            "staffing_decision_insufficient",
        )

    def test_unknown_or_low_confidence_candidate_abstains(self):
        unknown = validate_semantic_proposal("question", {
            "contract_id": "not-a-contract",
            "confidence": 1,
            "term_evidence": {},
        })
        self.assertEqual(unknown.path, RoutingPath.ABSTAIN)

        low = validate_semantic_proposal("อะไรก็ได้", {
            "contract_id": "finance_portfolio_totals",
            "confidence": 0.5,
            "term_evidence": {},
        })
        self.assertEqual(low.path, RoutingPath.ABSTAIN)

    def test_non_finite_confidence_and_unrelated_spans_abstain(self):
        question = "hello world foo bar"
        proposal = {
            "contract_id": "finance_portfolio_totals",
            "confidence": 0.99,
            "term_evidence": {
                "loan_amnt": "hello",
                "funded_amnt": "world",
                "ค่าเฉลี่ย": "foo",
                "พอร์ต": "bar",
            },
        }
        decision = validate_semantic_proposal(question, proposal)
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("missing grounded terms", decision.reason)

        proposal["confidence"] = math.nan
        non_finite = validate_semantic_proposal(question, proposal)
        self.assertEqual(non_finite.path, RoutingPath.ABSTAIN)
        self.assertIn("confidence", non_finite.reason)

    def test_semantic_synonym_cannot_bypass_negated_metric(self):
        cases = (
            (
                "สรุปพอร์ตทั้งหมด loan_amnt และ funded_amnt "
                "แต่ไม่เอาค่า mean",
                {
                    "contract_id": "finance_portfolio_totals",
                    "confidence": 0.99,
                    "reason": "wrongly ignored negation",
                    "term_evidence": {
                        "loan_amnt": "loan_amnt",
                        "funded_amnt": "funded_amnt",
                        "ค่าเฉลี่ย": "ค่า mean",
                        "พอร์ต": "พอร์ตทั้งหมด",
                    },
                },
            ),
            (
                "แจกแจง loan_status ทุกสถานะพร้อมจำนวน แต่ไม่เอา share",
                {
                    "contract_id": "finance_status_mix",
                    "confidence": 0.99,
                    "reason": "wrongly ignored negation",
                    "term_evidence": {
                        "loan_status": "loan_status",
                        "สัดส่วน": "share",
                        "ทุกสถานะ": "ทุกสถานะ",
                    },
                },
            ),
            (
                "summarize whole portfolio loan_amnt and funded_amnt but omit average",
                {
                    "contract_id": "finance_portfolio_totals",
                    "confidence": 0.99,
                    "reason": "wrongly ignored English negation",
                    "term_evidence": {
                        "loan_amnt": "loan_amnt",
                        "funded_amnt": "funded_amnt",
                        "ค่าเฉลี่ย": "average",
                        "พอร์ต": "whole portfolio",
                    },
                },
            ),
        )
        for question, proposal in cases:
            with self.subTest(question=question):
                decision = validate_semantic_proposal(question, proposal)
                self.assertEqual(decision.path, RoutingPath.ABSTAIN)
                self.assertIn("negated", decision.reason)

    def test_fixed_threshold_cannot_be_rebound_by_semantic_model(self):
        question = (
            "contract dependency มากกว่า 60% ของคนปฏิบัติงาน "
            "มีแผนกใดเข้าเกณฑ์"
        )
        proposal = {
            "contract_id": "strict_contract_dependency_policy",
            "confidence": 0.99,
            "reason": "wrong threshold proposal",
            "term_evidence": {
                "contract dependency": "contract dependency",
                "มากกว่า 50%": "มากกว่า 60%",
                "ปฏิบัติงาน": "ปฏิบัติงาน",
                "แผนกใด": "แผนกใด",
            },
        }
        decision = validate_semantic_proposal(question, proposal)
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("constraint", decision.reason)

    def test_wrong_bucket_edges_cannot_be_rebound(self):
        question = (
            "แบ่ง dti เป็นต่ำกว่า 5, 5 ถึงต่ำกว่า 15, "
            "15 ถึงต่ำกว่า 25, ตั้งแต่ 25 และข้อมูลว่าง"
        )
        proposal = {
            "contract_id": "finance_dti_buckets",
            "confidence": 0.99,
            "reason": "wrong boundary proposal",
            "term_evidence": {
                "dti": "dti",
                "<10": "ต่ำกว่า 5",
                "10-<20": "5 ถึงต่ำกว่า 15",
                "20-<30": "15 ถึงต่ำกว่า 25",
                "30+": "ตั้งแต่ 25",
                "NULL": "ข้อมูลว่าง",
                "แบ่ง": "แบ่ง",
            },
        }
        decision = validate_semantic_proposal(question, proposal)
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("constraint", decision.reason)

    def test_all_employee_population_cannot_bind_to_active_contract(self):
        decision = validate_semantic_proposal(
            "นับพนักงานทั้งหมดแยกตามแผนก",
            {
                "contract_id": "active_headcount_by_department",
                "confidence": 0.99,
                "reason": "incorrectly treated all as active",
                "term_evidence": {},
            },
        )
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("active_employee_population", decision.reason)

    def test_top_three_cannot_bind_to_top_two_contract(self):
        question = (
            "โครงการสามรายการที่มี project_value สูงสุด"
            "กินสัดส่วนมูลค่ารวมเกิน 60% หรือไม่"
        )
        decision = validate_semantic_proposal(question, {
            "contract_id": "top_two_project_concentration",
            "confidence": 0.99,
            "reason": "wrong top-n proposal",
            "term_evidence": {},
        })
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("top_project_count", decision.reason)

        mixed = route_metric_contract(
            "คำนวณ concentration risk ของ project_value สูงสุด "
            "เกิน 60% โดยไม่เอา top 2 ให้ใช้ top 3",
            semantic=False,
        )
        self.assertEqual(mixed.path, RoutingPath.ABSTAIN)

    def test_unlisted_bucket_boundary_cannot_bind(self):
        question = (
            "แบ่ง dti เป็นต่ำกว่า 10, 10 ถึงต่ำกว่า 20, "
            "20 ถึงต่ำกว่า 30, ตั้งแต่ 30 และข้อมูลว่าง "
            "แต่ขอเพิ่มจุดแบ่ง 25"
        )
        decision = validate_semantic_proposal(question, {
            "contract_id": "finance_dti_buckets",
            "confidence": 0.99,
            "reason": "wrong extra boundary",
            "term_evidence": {},
        })
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("unlisted numeric", decision.reason)

    def test_expected_and_conflicting_values_together_abstain(self):
        questions = (
            (
                "funded_amnt และ int_rate แต่ละปี 2016 ถึง 2020 "
                "โดยใช้ 2019 เป็นปีฐาน"
            ),
            (
                "contract dependency มากกว่า 50% เดิม แต่ขอใช้ 60% "
                "สำหรับคนปฏิบัติงาน แผนกใดเข้าเกณฑ์"
            ),
            (
                "นับพนักงานปฏิบัติงานและพนักงานทั้งหมดแยกตาม department"
            ),
        )
        for question in questions:
            with self.subTest(question=question):
                decision = route_metric_contract(question, semantic=False)
                self.assertEqual(decision.path, RoutingPath.ABSTAIN)

    def test_expected_value_with_conflicting_operator_abstains(self):
        questions = (
            (
                "contract dependency มากกว่า 50% เดิม "
                "แต่ใช้ไม่น้อยกว่า 50% กับคนปฏิบัติงาน แผนกใดเข้าเกณฑ์"
            ),
            (
                "performance review coverage ปี 2023 ของคนปฏิบัติงาน "
                "เกณฑ์ 80% เดิม แต่ใช้มากกว่า 80%"
            ),
            (
                "training_type ใดมี concentration ชั่วโมงอบรมมากกว่า 50% "
                "เดิม แต่ใช้ตั้งแต่ 50%"
            ),
        )
        for question in questions:
            with self.subTest(question=question):
                decision = route_metric_contract(question, semantic=False)
                self.assertEqual(decision.path, RoutingPath.ABSTAIN)

    def test_valid_gte_operator_phrases_are_not_misread_as_negation(self):
        for phrase in ("ไม่น้อยกว่า", "อย่างน้อย", "ตั้งแต่"):
            question = (
                "ตรวจ performance review coverage ปี 2023 "
                f"ของพนักงานปฏิบัติงานทั้งองค์กร {phrase} 80%"
            )
            proposal = {
                "contract_id": "performance_review_coverage",
                "confidence": 0.99,
                "reason": "valid inclusive threshold",
                "term_evidence": {
                    "performance review": "performance review",
                    "coverage": "coverage",
                    "80%": f"{phrase} 80%",
                },
            }
            with self.subTest(phrase=phrase):
                decision = validate_semantic_proposal(question, proposal)
                self.assertEqual(decision.path, RoutingPath.SEMANTIC)

    def test_word_form_explicit_override_fails_closed(self):
        question = (
            "contract dependency เกินครึ่งเดิม "
            "แต่ใช้ไม่น้อยกว่าครึ่งสำหรับพนักงานปฏิบัติงาน"
        )
        decision = validate_semantic_proposal(question, {
            "contract_id": "strict_contract_dependency_policy",
            "confidence": 0.99,
            "reason": "conflicting word-form operator",
            "term_evidence": {},
        })
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("override", decision.reason)

    def test_auxiliary_band_count_is_not_mistaken_for_boundary(self):
        question = (
            "เฉพาะ Individual แบ่ง annual_inc เป็น 4 ช่วงคงที่ "
            "ต่ำกว่า 50000, 50000 ถึงต่ำกว่า 70000, "
            "70000 ถึงต่ำกว่า 100000 และ 100000 ขึ้นไป"
        )
        decision = validate_semantic_proposal(question, {
            "contract_id": "finance_fixed_income_bands",
            "confidence": 0.99,
            "reason": "four fixed bands",
            "term_evidence": {
                "Individual application population": "Individual",
                "annual income field": "annual_inc",
                "four fixed income bands": "4 ช่วงคงที่",
            },
        })
        self.assertEqual(decision.path, RoutingPath.SEMANTIC)

    def test_joint_app_cannot_bind_to_individual_income_contract(self):
        question = (
            "เฉพาะ Joint App แบ่ง annual_inc เป็นช่วงรายได้"
            "ต่ำกว่า 50000, 50000 ถึงต่ำกว่า 70000, "
            "70000 ถึงต่ำกว่า 100000 และตั้งแต่ 100000 ขึ้นไป"
        )
        decision = validate_semantic_proposal(question, {
            "contract_id": "finance_fixed_income_bands",
            "confidence": 0.99,
            "reason": "wrong population proposal",
            "term_evidence": {},
        })
        self.assertEqual(decision.path, RoutingPath.ABSTAIN)
        self.assertIn("individual_application_population", decision.reason)

    def test_postfix_negation_cannot_admit_a_fixed_value(self):
        top = route_metric_contract(
            "project_value สูงสุด top 2 ไม่เอา ให้ใช้ top 3 "
            "คำนวณ concentration เกิน 60%",
            semantic=False,
        )
        self.assertEqual(top.path, RoutingPath.ABSTAIN)

        individual = validate_semantic_proposal(
            "Individual ไม่ใช้ ให้ใช้ Joint App กับ annual_inc "
            "ต่ำกว่า 50000, 50000 ถึงต่ำกว่า 70000, "
            "70000 ถึงต่ำกว่า 100000 และ 100000 ขึ้นไป",
            {
                "contract_id": "finance_fixed_income_bands",
                "confidence": 0.99,
                "reason": "postfix-negated population",
                "term_evidence": {},
            },
        )
        self.assertEqual(individual.path, RoutingPath.ABSTAIN)
        self.assertIn("negated", individual.reason)

    def test_negated_or_schema_only_literal_matches_abstain(self):
        questions = (
            "ไม่ต้องการค่าเฉลี่ย loan_amnt หรือ funded_amnt ของพอร์ตทั้งหมด",
            "อย่านับพนักงานปฏิบัติงานแยกตาม department แค่อธิบาย schema",
            "ไม่ต้องแจกแจง loan_status ทุกสถานะหรือสัดส่วน ขอ schema เท่านั้น",
        )
        for question in questions:
            with self.subTest(question=question):
                decision = route_metric_contract(question, semantic=False)
                self.assertEqual(decision.path, RoutingPath.ABSTAIN)
                self.assertIsNone(decision.contract_id)

    def test_mid_sentence_negated_contract_terms_do_not_route_lexically(self):
        questions = (
            "สรุปพอร์ตทั้งหมด loan_amnt และ funded_amnt แต่ไม่ต้องการค่าเฉลี่ย",
            "แจกแจง loan_status ทุกสถานะพร้อมจำนวน แต่ไม่ต้องการสัดส่วน",
            "จำแนก emp_length ที่ funded_amnt สูงสุดและต่ำสุด แต่ไม่รวม N/A",
        )
        for question in questions:
            with self.subTest(question=question):
                decision = route_metric_contract(question, semantic=False)
                self.assertEqual(decision.path, RoutingPath.ABSTAIN)
                self.assertIsNone(decision.contract_id)


if __name__ == "__main__":
    unittest.main()

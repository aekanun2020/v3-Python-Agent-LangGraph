# Unseen Paraphrase + Boundary Evaluation

ชุดนี้วัดว่า contract selector จับ paraphrase ได้หรือไม่ และรู้จัก abstain
เมื่อคำถามอยู่นอกขอบเขต contract โดยแยกจากการตรวจความถูกต้องของ
MCP evidence และคำตอบปลายทาง

## สิ่งที่ถูก freeze

- `*_unseen_paraphrases.json`: คำถามที่ควรเลือก contract ที่ระบุ
- `*_boundaries.json`: near-boundary questions ที่ส่วนใหญ่ต้อง abstain
- `semantic_v2_corrections.json`: overlay แก้ ground truth ที่ตรวจพบจาก pre-run
  contract audit โดยไม่แก้ไฟล์ v1 เดิม
- `semantic_v3_corrections.json`: overlay ต่อจาก v2 เพื่อให้คำถามระบุ
  fixed business value ที่ executable contract กำหนด

ห้ามแก้คำถามหลังเห็นผลเพื่อทำให้ score ดีขึ้น ถ้าพบ defect ให้เก็บไฟล์
เดิมไว้เป็น audit trail และออก suite version ใหม่แบบเดียวกับ
`semantic-v2` และ `semantic-v3`

## Suite versions

| Version | หน้าที่ | ควรใช้เมื่อ |
|---|---|---|
| `frozen-v1` | ไฟล์คำถามดั้งเดิมก่อน audit | ทำซ้ำ historical baseline และตรวจ audit trail |
| `semantic-v2` | v1 + correction overlay 5 รายการ | ตรวจประวัติ router v2 |
| `semantic-v3` | v2 + fixed-constraint correction 1 รายการ | ประเมิน router ปัจจุบัน (ค่าเริ่มต้น) |

Correction overlay มี 5 รายการ:

| Case | ข้อแก้ไขเชิงความหมาย |
|---|---|
| `hr_para_004` | contract มี grain ระดับทั้งองค์กร ไม่ใช่รายแผนก |
| `hr_para_007` | top two ต้องอ้างลำดับตาม `project_value` |
| `hr_boundary_005` | คำขอ staffing decision ที่หลักฐานไม่พอควร route เข้า fail-closed refusal contract ไม่ใช่ abstain |
| `fin_para_008` | fixed income bands ต้องระบุขอบ 70,000 ด้วย |
| `fin_para_010` | dual-risk screen ต้องระบุทั้ง interest rate และ Charged Off rate |

`semantic-v3` แก้ `hr_para_004` ให้ระบุ `review_period=2023`
ซึ่งเป็น fixed value ใน performance-review contract ที่ v2 ยังไม่ได้ระบุ

Score ของ `frozen-v1`, `semantic-v2` และ `semantic-v3` ไม่ควรถูกนำมา
เปรียบเทียบโดยไม่ระบุ version เพราะ expected questions/labels ต่างกันบางจุด

## Routing modes

### `legacy`

ใช้ substring/literal `question_terms_all/any` เท่านั้น ไม่เรียก LLM หรือ MCP

### `hybrid` (ค่าเริ่มต้น)

```text
lexical fast path
  -> request-boundary guard: negation/schema-only ให้ abstain
  -> exact terms หรือ Skill-declared high-precision lexical aliases
  -> unique match + typed constraints: รับ route โดยไม่เรียก Router LLM
  -> zero/ambiguous match: ขอ semantic proposal 1 ครั้ง
       -> deterministic contract-id + anchor + typed-constraint
          + exact-span/concept-pattern/negation gate
       -> contract หรือ abstain
```

Hybrid routing อาจเรียก OpenRouter แต่ไม่เรียก MCP จนกว่าจะใส่ `--live`
Semantic output เป็น routing metadata ไม่ใช่ evidence และถ้า timeout/output ผิดรูป/
หลักฐานคำไม่ครบ ระบบจะ abstain แบบ fail-closed

## วิธีรัน

Historical baseline ที่ทำซ้ำได้:

```bash
python scripts/evaluate_skill_routing.py \
  --suite-version frozen-v1 \
  --routing-mode legacy \
  --allow-failures \
  --output artifacts/frozen_v1_legacy_baseline.json
```

ตั้งแต่ v3 evaluator จะ exit nonzero เมื่อมี routing/live failure
ใส่ `--allow-failures` เฉพาะเมื่อตั้งใจเก็บ exploratory หรือ historical baseline

Hybrid semantic evaluation (ใช้ OpenRouter key):

```bash
ROUTER_MODEL=openai/gpt-oss-120b \
python scripts/evaluate_skill_routing.py \
  --suite-version semantic-v3 \
  --routing-mode hybrid \
  --workers 1 \
  --progress \
  --output artifacts/v3_semantic_router_acceptance_run.json
```

Acceptance runs ใช้ `--workers 1` เพื่อวัด sequential request latency
ส่วน `--workers` ที่มากกว่า 1 ทำให้เฉพาะ evaluation เรียก semantic router แบบขนาน;
output ยังเรียงตาม case order เดิม ไม่ได้เปลี่ยน agent runtime ให้เรียก router
มากกว่าหนึ่งครั้งต่อคำขอ

รันค่าเริ่มต้นของ repo แบบสั้น:

```bash
make evaluate-routing
```

Make target ใช้ `semantic-v3`, `hybrid` และไม่ใส่ `--allow-failures`

รัน routing แล้วตรวจ contract evidence กับ MCP จริง:

```bash
ROUTER_MODEL=openai/gpt-oss-120b \
python scripts/evaluate_skill_routing.py \
  --suite-version semantic-v3 \
  --routing-mode hybrid \
  --live \
  --output artifacts/v3_semantic_router_acceptance_live.json
```

`--live` เรียก MCP เฉพาะ paraphrase ที่ route ถูก และรันเพียงหนึ่งครั้งต่อ
contract id ที่ไม่ซ้ำ จึงไม่ใช่ end-to-end agent-answer evaluation

## Metrics และ fingerprint

- `contract_recall`: paraphrases ที่เลือก expected contract ถูก
- `boundary_accuracy`: near-boundary cases ที่ได้ expected route หรือ abstain ถูก
- `boundary_precision`: alias เก่าของ `boundary_accuracy` เพื่อให้ report v1 ยังอ่านได้
- `false_match_rate`: สัดส่วน negative boundaries (`expected_contract=null`)
  ที่ถูก route เข้า contract ผิด
- `missed_safe_boundary_routes`: boundary ที่ควรเข้า refusal contract
  แต่ selector ไม่ route ตาม expected contract
- `lexical_routes`, `semantic_attempts`, `semantic_routes`, `abstentions`:
  จำนวนการตัดสินใจตามเส้นทางจริง
- `routing_median_seconds`, `semantic_median_seconds`,
  `semantic_p95_seconds`: latency ที่วัดในรอบนั้น
- `live_contract_completion`: live MCP roles ที่ evidence ครบตาม contract
- `live_answer_completion`: contract-composed answers ที่มี emitted claims ไม่ว่าง

ผล hybrid ทุกไฟล์มี `router_fingerprint` ซึ่งรวม prompt version,
deterministic gate version/source hash, catalog hash, model, timeout, max output
tokens, reasoning effort และ confidence threshold
การเปรียบเทียบรอบต้องใช้ fingerprint เดียวกัน

## ผลที่มีอยู่

Historical `frozen-v1 + legacy` baseline อยู่ที่
[`artifacts/unseen_boundary_baseline_report.md`](../../artifacts/unseen_boundary_baseline_report.md):
paraphrase recall `55%`, boundary accuracy `95%`, false match `5%`; live MCP
ผ่าน `11/11` contracts สามรอบด้วย normalized evidence hash เดียวกัน

Final `semantic-v3 + hybrid` sequential acceptance artifacts ที่มี router
fingerprint เดียวกันบันทึก paraphrase `20/20` และ boundary `20/20`
ทั้งสองรอบโดยไม่มี false match; decision projection SHA-256 เท่ากับ
`e4b45b61f53ce754374629939f202567ced3f0bb3a9b5f90b66829ba57e3e50a`
gate source SHA-256 คือ
`611aa9d67bddfe7405df36bc61ba63aa71599f13976a742c2d6cccb116eefcab`
และ catalog SHA-256 คือ
`ed3112d6292f38d4d51d068895a6659233f6b75c8d0a342607183f1a018c4377`
run 1 ผ่าน live MCP `20/20` contracts และได้คำตอบไม่ว่าง `20/20` ดู
[acceptance report](../../artifacts/v3_semantic_router_acceptance_report.md)

เหตุการณ์จริงจาก v2 แยกเป็น manifest ที่
[`v2_incidents.json`](v2_incidents.json) และ replay ด้วย
`scripts/replay_v2_incidents.py`; หลังแก้ regression ที่ suite พบ live run 2–3
ผ่าน incidents `17/17`, routing `40/40` และ contracts `6/6` ต่อรอบ

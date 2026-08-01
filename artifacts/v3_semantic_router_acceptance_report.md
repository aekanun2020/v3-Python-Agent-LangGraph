# v3 Hybrid Contract Router — Acceptance Report

วันที่ทดสอบ: 2026-08-01 (Asia/Bangkok)

## ข้อสรุป

`hybrid-contract-router-v3` ผ่าน acceptance suite สองรอบแบบ sequential:

- paraphrases `20/20` และ near-boundaries `20/20` ทั้งสองรอบ
- false matches `0`
- decision projection SHA-256 เหมือนกันทั้งสองรอบ:
  `ccf0fda7ea1de47c13ba7f234e7caf139a11b189f4346cecdfbef4ef862eb87d`
- live MSSQL MCP contract completion `20/20` และ non-empty answers `20/20`

ผลนี้พิสูจน์เฉพาะ 20 declared intent paraphrases และ 20 near-boundary
cases ของ HR/Finance Skills ใน suite นี้ ไม่ใช่การรับรองทุกคำถามหรือ
production readiness

## สถาปัตยกรรมที่ทดสอบ

```text
Question
  -> reject explicit negated operation / negative-only / schema-only request
  -> exact terms + Skill-declared high-precision lexical aliases
  -> deterministic entity/concept identity + polarity/operator + typed-constraint gate
       -> one unique contract: accept lexical route
       -> zero/ambiguous: one semantic proposal, no retry
            -> deterministic known-id + entity/metric/grain identity
               + concept/polarity/operator + typed-constraint + confidence
               + exact-span/concept-pattern/negation gate
            -> contract or fail-closed abstain
```

Router output เป็น routing metadata เท่านั้น ไม่ใช่ accepted evidence และไม่สามารถ
แก้ MCP query, completion rule, claim allowlist หรือ fixed business values
ใน executable contract

### Contract-owned typed constraints

Fixed semantics อยู่ใน `skills/*/references/answer_contracts.json` ไม่ได้ฝากไว้ใน
prompt หรือ model output โดย runtime รองรับ typed constraints สี่แบบ:

- `comparison`
- `ordered_boundaries`
- `closed_range`
- `fixed_value`

โมเดลเห็นค่าคงที่เหล่านี้เพื่อเสนอ intent แต่ Python ต้องพิสูจน์ทุก required
pattern group จากคำถามอีกครั้ง ถ้าพิสูจน์ไม่ได้ให้ abstain
ทุก query-affecting parameter ใน answer contract ต้อง bind กับ typed constraint
และค่าต้องตรงกัน ไม่เช่นนั้น runtime จะปฏิเสธ catalog แบบ fail-closed
ก่อน route ใด ๆ

### Request-boundary guard

ก่อนทั้ง lexical และ semantic path ระบบปฏิเสธ:

- operation ที่ถูกปฏิเสธอย่างชัดเจน เช่น “อย่านับ…”
- negative-only request ที่ไม่มี positive operation ให้ทำ
- คำขอที่ต้องการเพียง schema/โครงสร้างตาราง ไม่ได้ขอรัน metric contract

คำเตือนกลางประโยคที่กำหนดขอบเขตการตีความ เช่น “แต่อย่าตีความเป็น
ผลิตภาพ” ไม่ถูกเหมาว่าเป็น negative-only request

### High-precision lexical aliases

Skill สามารถประกาศ `lexical_pattern_groups` ใน routing catalog เพื่อรองรับ paraphrase
ที่ precision สูงโดยไม่เรียก LLM ทุก pattern group ต้องมีอย่างน้อยหนึ่ง
regex ที่ match และ route ยังต้องผ่าน anchors/typed constraints

สำหรับ semantic proposal คำคัดลอกจากคำถามต้องตรงกับ Skill-owned
`concept_evidence_patterns` ของ concept ที่โมเดลอ้าง และต้องไม่ถูก negated
จึงป้องทั้งการนำ generic span เดียวไปปลอมเป็นหลาย concept และการใช้
คำที่ผู้ใช้ปฏิเสธเป็นหลักฐานสนับสนุน
นอกจากนี้ required concepts ต้องพิสูจน์ชนิด entity, metric และ grain ของ
contract โดยตรง เพื่อไม่ให้คำที่มี operation คล้ายกันแต่พูดถึงคนละสิ่ง
เข้า contract ผิด และ polarity/operator gate ต้องปฏิเสธ negated metric
หรือเกณฑ์เปรียบเทียบที่กลับทิศ

## Suite history และ ground-truth audit

ไฟล์ `frozen-v1` ถูกเก็บไว้โดยไม่แก้ หลัง pre-run contract audit พบ ground-truth
defects 5 จุด จึงสร้าง `semantic-v2` overlay:

- แก้ performance coverage จาก department grain เป็น organization grain
- ระบุ top two ตาม `project_value` ไม่ใช่สองแถวแรก
- route คำขอ staffing decision ที่ข้อมูลไม่พอเข้า safe refusal contract
- เพิ่ม fixed-income boundary 70,000 ที่ขาดหาย
- ระบุทั้ง interest-rate และ Charged-Off metric ใน dual-risk screen

Typed-constraint audit จาก v2 พบอีก 1 จุด จึงสร้าง `semantic-v3` overlay:

- `hr_para_004` ต้องระบุ `review_period=2023` ตาม fixed value ใน contract

ห้ามเปรียบเทียบ score ข้าม `frozen-v1`, `semantic-v2` และ `semantic-v3`
โดยไม่ระบุ suite version

## ผลเปรียบเทียบ

| Selector / suite | Paraphrases | Near-boundary | False matches |
|---|---:|---:|---:|
| Legacy literal / frozen-v1 | 11/20 (55%) | 19/20 (95%) | 1 |
| Legacy literal / semantic-v2 | 11/20 (55%) | 20/20 (100%) | 0 |
| Hybrid v3 / semantic-v3 — acceptance run 1 | 20/20 (100%) | 20/20 (100%) | 0 |
| Hybrid v3 / semantic-v3 — acceptance run 2 | 20/20 (100%) | 20/20 (100%) | 0 |

ทั้งสอง acceptance runs ใช้ fingerprint เดียวกัน:

- prompt: `hybrid-contract-router-v3`
- deterministic gate: `skill-grounded-admission-gate-v1`
- gate source SHA-256:
  `611aa9d67bddfe7405df36bc61ba63aa71599f13976a742c2d6cccb116eefcab`
- catalog SHA-256:
  `b04c656c71e0c66c964341ecc233519780fc59af75070f1c92dbc6dddaf03034`
- router model: `openai/gpt-oss-120b`
- timeout: 30 seconds, no retry
- max output: 1,600 tokens, reasoning effort: low
- confidence gate: 0.80

## Router paths และ latency

ทั้งสองรอบมี lexical routes 13, semantic routes 8, semantic attempts 27
และ abstentions 19 เท่ากัน

| Run | Routing median | Semantic median | Semantic p95 |
|---|---:|---:|---:|
| Acceptance 1 | 4.045236s | 4.807690s | 10.413516s |
| Acceptance 2 | 3.489238s | 4.325542s | 10.446251s |

ตัวเลขนี้วัด sequential (`--workers 1`) ให้ใกล้เคียงกับหนึ่ง request ต่อครั้ง
ไม่ใช่ throughput benchmark และไม่ได้หมายความว่า LLM path เป็น deterministic

## Live MSSQL MCP และ Agent E2E

Acceptance run 1 รัน query roles ของ contract ที่ route ถูกกับ MCP จริง:

- contract completion: `20/20`
- non-empty contract-composed answers: `20/20`
- normalized evidence SHA-256:
  `e4471a2337e3fe8df765ec446789c2a6bf5529d1a42c0289b0664ca7ae92ab91`

ทดสอบ entry point จริงแบบ E2E ด้วย:

```bash
python labs/lab6_todo/agent_todo.py \
  "นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก"
```

ผลคือค้นพบ MCP tools 5 ตัว, route แบบ `semantic` เข้า
`active_headcount_by_department` ด้วย confidence `0.99`, รัน role
`grouped_active_headcount`, ผ่าน terminal approval และตอบพนักงานรวม
25 คนพร้อมจำนวนของทั้ง 8 แผนกที่ตรงกับ accepted evidence

Artifacts:

- [`v3_semantic_router_acceptance_run1.json`](v3_semantic_router_acceptance_run1.json)
- [`v3_semantic_router_acceptance_run2.json`](v3_semantic_router_acceptance_run2.json)

## Automated tests

- non-Lab 8 suite: `113 passed` + 35 subtests
- Lab 8 separate unittest: `2 passed`

```bash
python -m pytest tests --ignore=tests/test_lab8_planner.py -q
python -m unittest -v tests.test_lab8_planner
```

## วิธีรัน acceptance ซ้ำ

```bash
ROUTER_MODEL=openai/gpt-oss-120b \
python scripts/evaluate_skill_routing.py \
  --suite-version semantic-v3 \
  --routing-mode hybrid \
  --workers 1 \
  --progress \
  --live \
  --output artifacts/v3_semantic_router_acceptance_run.json
```

Evaluator จะ exit nonzero เมื่อ routing, contract completion หรือ answer completion
ไม่ผ่าน ใส่ `--allow-failures` เฉพาะเมื่อตั้งใจเก็บ exploratory/historical
baseline ที่รู้ว่าไม่ผ่าน

## ขอบเขตของข้อสรุป

ผลนี้พิสูจน์ว่า hybrid selector ดีกว่า literal baseline บน suite ที่ระบุ
และเส้นทางที่เลือกสามารถทำ contract roles ครบ พร้อมประกอบคำตอบ
จาก accepted evidence

ผลนี้ยังไม่รับรอง domain อื่น, paraphrase ทุกแบบ, provider availability,
causal inference หรือ individual decision quality ตัว semantic proposal ยังเป็น
LLM จึงต้องคง fail-closed gate, abstention, fingerprint และ repeated evaluation

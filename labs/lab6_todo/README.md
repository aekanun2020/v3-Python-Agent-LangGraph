# Lab 6 — Pure Python Agent: Hybrid Routing, Observation, Evidence และ Skill Contracts

Lab นี้เริ่มจาก TodoWrite แบบ Pure Python แล้วพัฒนาเป็น agent runtime ที่แยก
การวางแผน การเรียก MCP การรับหลักฐาน และการตรวจคำตอบออกจากกันอย่างชัดเจน
โดยไม่ใช้ LangGraph

เป้าหมายปัจจุบันไม่ใช่ทำให้ LLM “ตอบเก่งทุกเรื่อง” แต่ทำให้คำตอบใน bounded
domain ตรวจสอบย้อนกลับได้ และไม่ปล่อย claim ที่เกินหลักฐาน

## สิ่งที่ผู้เรียนจะเห็น

- `TodoState` เก็บแผนงานหลายขั้นในหน่วยความจำ
- `ContextState` เก็บ goal, phase, action/error signatures และ budgets
- `EvidenceState` เก็บผล MCP ที่ผ่านการยอมรับพร้อม provenance
- Dynamic Observation ตรวจผลหลัง tool call และเลือก
  `accept / query_more / replan / stop`
- deterministic checks ตรวจ error, query role, grain, field, label และความครบ
- Hybrid Contract Router ใช้ lexical fast path ก่อน แล้วค่อยขอ semantic
  candidate เมื่อ lexical ไม่ชัด
- LLM Semantic Observer ถูกเรียกเฉพาะเส้นทางทั่วไปที่มีความเสี่ยงด้านความหมาย
- Claim Gate ประกอบคำตอบแบบ fail-closed จาก claim ที่ตรวจแล้ว
- Skill contracts ให้ semantics และ acceptance criteria ของ bounded domain

## สถาปัตยกรรมปัจจุบัน

```text
User question
      |
      v
Negation / schema-only request guard
      |
      +-- explicit non-request ----------------> abstain
      |
      v
Exact terms + high-precision lexical aliases
      |
      +-- unique + anchors + typed constraints -> selected contract
      |
      +-- zero/ambiguous match
                 |
                 v
        one semantic proposal (ROUTER_MODEL)
                 |
                 v
        deterministic id/concept/polarity/operator/constraint/span gate
                 |
          +------+- fail ----------------------> abstain
          |                                      |
          v                                      v
   selected contract                     Pure Python Agent loop
          |                              Plan -> MCP -> Observe
          v                                      |
 contract-declared MCP query                     v
          |                              deterministic checks
          v                                      |
 evidence completeness                   semantic risk?
          |                                |          |
          v                               no         yes
 fail-closed Claim Gate                    |          |
          |                                |          v
          v                                |      LLM Observer
        Answer                             +----------+
                                                     |
                                                     v
                                                Claim Gate
                                                     |
                                                     v
                                                   Answer
```

การเลือก contract ใน v3 มีลำดับดังนี้:

1. กันคำขอที่ negation ปฏิเสธ operation, negative-only หรือขอ schema เท่านั้น
   ก่อนทั้ง lexical และ semantic path
2. หา literal matches จาก `question_terms_all/any` รวมกับ
   Skill-declared `lexical_pattern_groups` ที่ออกแบบให้ precision สูง
3. ตรวจ entity/metric identity, critical anchors แบบ positive match,
   comparison operator และ
   typed `routing_constraints` จาก executable
   answer contract เช่น comparison, ordered boundaries, closed range และ fixed value
   ทุก query-affecting parameter ต้อง bind กับ constraint และมีค่าตรงกัน
   ไม่เช่นนั้น runtime จะปฏิเสธ catalog เพื่อป้อง routing/query drift
4. ถ้าเหลือเพียง contract เดียว รับทันทีโดยไม่เรียก Router LLM
5. ถ้าไม่มี match หรือกำกวม เรียก `ROUTER_MODEL` เพียงหนึ่งครั้งให้เสนอ
   candidate หรือ abstain
6. Python รับ candidate เฉพาะเมื่อ contract id รู้จัก, entity/metric/grain
   identity ตรงกัน, confidence ถึงเกณฑ์, concept evidence ครบ,
   critical anchors เป็น positive match และ operator ตรง contract
   และ contract-owned constraints ครบ รวมถึง evidence spans
   เป็นข้อความจริงที่คัดลอกจากคำถาม, ไม่ถูก negated และตรงกับ
   Skill-owned `concept_evidence_patterns` ของ concept นั้นจริง
7. ถ้า output ผิดรูป, timeout, id ไม่รู้จัก, constraint พิสูจน์ไม่ได้
   หรือหลักฐานคำไม่ครบ ให้ abstain
   แบบ fail-closed ไม่เดา contract

Semantic proposal เป็น routing metadata ไม่ใช่ accepted evidence
และไม่มีอำนาจผ่าน Claim Gate ส่วนคำถามที่ abstain จะเข้า general
agent loop และ semantic-risk routing ตามเดิม

## Contract และ Skill คืออะไร

Contract คือ executable business specification ซึ่งกำหนด:

- intent family และคำที่ใช้เลือก contract
- MCP query roles และ read-only query template
- table, filter, grain และ field ที่ต้องพบ
- output columns, canonical labels และ arithmetic ที่อนุญาต
- terminal verdict, grounded notes และข้อห้ามทางความหมาย

Observation เป็นกลไกทั่วไป แต่ไม่รู้ business semantics ด้วยตัวเอง จึงต้องรับ
acceptance criteria จาก Skill:

```text
Skill          = ความรู้และข้อกำหนดของ bounded domain
Contract       = นิยามที่ runtime ตรวจได้ว่า evidence ถูกและครบหรือไม่
Observation    = ตัดสินผล tool เทียบกับ contract และ state ปัจจุบัน
Claim Gate     = อนุญาตเฉพาะ claim ที่พิสูจน์แล้วออกสู่คำตอบ
```

## ตำแหน่งของ contracts

Generic runtime ค้นหาไฟล์:

```text
skills/*/references/answer_contracts.json
```

Semantic router ค้นหา catalog จาก Skill แยกจาก executable
answer contract:

```text
skills/*/references/routing_catalog.json
```

Catalog เป็นเพียงขอบเขต intent/exclusion และ high-precision lexical aliases
สำหรับเสนอ route; business acceptance criteria รวมถึง typed fixed constraints
ที่มีอำนาจยังอยู่ใน `answer_contracts.json`

Skill ที่มีอยู่:

- [`skills/hr-analytics`](../../skills/hr-analytics/SKILL.md)
- [`skills/finance-analytics`](../../skills/finance-analytics/SKILL.md)

ไฟล์ [`executable_metric_contracts.json`](executable_metric_contracts.json)
ตั้งใจให้ไม่มี domain contract (`"contracts": []`) เพื่อยืนยันว่า runtime core
ไม่ผูกกับ HR หรือ Finance

## วิธีรัน

รันจาก root repository เสมอ:

```bash
conda activate agentic-ai
cd v3-Python-Agent-LangGraph

python labs/lab6_todo/agent_todo.py \
  "นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก"
```

ตัวอย่างคำถาม Finance:

```bash
python labs/lab6_todo/agent_todo.py \
  "สรุปจำนวนรายการและยอด loan_amnt กับ funded_amnt รวมทั้งพอร์ต"
```

ถ้าไม่ส่งคำถาม โปรแกรมจะเปิด interactive prompt:

```bash
python labs/lab6_todo/agent_todo.py
```

ตัวเลือกสำหรับการทดลองเปรียบเทียบ:

```bash
# ปิด LLM Final Semantic Observer
python labs/lab6_todo/agent_todo.py --semantic-observer off "คำถาม"

# ปิด Dynamic Observation/Claim Ledger เพื่อดู baseline path
python labs/lab6_todo/agent_todo.py --dynamic-observer off "คำถาม"

# กำหนด hard wall-clock deadline
python labs/lab6_todo/agent_todo.py --max-run-seconds 120 "คำถาม"

# ใช้ Hybrid Router (ค่าเริ่มต้น)
python labs/lab6_todo/agent_todo.py --contract-routing hybrid "คำถาม"

# ปิด semantic fallback เพื่อเปรียบเทียบ selector แบบ literal เดิม
python labs/lab6_todo/agent_todo.py --contract-routing lexical "คำถาม"
```

`--dynamic-observer off` จะปิด semantic contract fallback ด้วย เพราะโหมดนี้มีไว้เพื่อ
ทดลอง baseline ของ Observation/Claim Ledger

## Environment

คัดลอก `.env.example` เป็น `.env` และใส่ค่าจริง:

```dotenv
OPENROUTER_API_KEY=your-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=qwen/qwen3.5-35b-a3b
OBSERVER_MODEL=openai/gpt-oss-120b
ROUTER_MODEL=openai/gpt-oss-120b
ROUTER_TIMEOUT_SECONDS=30
MCP_SERVER_URL=https://your-mcp-server.example/mcp
```

`OPENROUTER_MODEL` ใช้กับ planning, tool selection และคำตอบบน general path
ส่วน `OBSERVER_MODEL` ใช้ตรวจความหมายเมื่อ risk router เห็นว่าจำเป็น หากไม่ตั้ง
`OBSERVER_MODEL` ระบบจะใช้ `OPENROUTER_MODEL`

`ROUTER_MODEL` ใช้เฉพาะเมื่อ lexical fast path ไม่ได้ unique contract;
ถ้าไม่ตั้งจะใช้ `OPENROUTER_MODEL` และ `ROUTER_TIMEOUT_SECONDS` จำกัดเวลาของ
semantic proposal ถ้า timeout ระบบจะ abstain โดยไม่ retry route

## ไฟล์สำคัญ

| ไฟล์ | หน้าที่ |
|---|---|
| `agent_todo.py` | entry point, TodoWrite, agent loop และ contract fast path |
| `context_state.py` | control state และ runtime budgets |
| `evidence_state.py` | evidence/observation types และ provenance |
| `evidence_contract.py` | ค้นหา Skill contracts, ตรวจ evidence และประกอบ contract claims |
| `contract_router.py` | lexical fast path, semantic proposal และ deterministic anchor/span gate |
| `dynamic_observer.py` | post-tool observation และ claim ledger |
| `risk_router.py` | deterministic observation และ semantic-risk routing |
| `semantic_observer.py` | LLM observer สำหรับความเสี่ยงด้านความหมาย |
| `claim_gate.py` | verify-then-emit แบบ fail-closed |
| `phase2_runtime.py` | MCP/LLM budgets และ hard deadline |

## ผลที่พิสูจน์แล้ว

### HR Skill

| Run | Questions | Atomic items | Median |
|---|---:|---:|---:|
| HR run 4 | 10/10 | 77/77 | 0.710s |
| HR run 5 | 10/10 | 77/77 | 0.706s |

สองรอบได้ answer hash เดียวกัน:
`af20423f90d8b38b2469691032831cf67efa7f2da81868056ed391b015ed51f9`

ดู [HR report](../../artifacts/hr_skill_run4_run5_report.md)

### Finance Skill

| Run | Questions | Atomic items | Median |
|---|---:|---:|---:|
| ก่อน Finance Skill | 2/10 | — | 97.591s |
| Finance run 3 | 10/10 | 148/148 | 0.792s |
| Finance run 4 | 10/10 | 148/148 | 0.730s |

หลังเพิ่ม HR Skill แล้ว Finance non-regression ยังคง `10/10`, `148/148`
และได้ answer hash เดิม

ดู [Finance report](../../artifacts/finance_skill_run3_run4_report.md)

## สิ่งที่ผลทดลองยังไม่พิสูจน์

- ไม่ได้รับรองคำถาม HR/Finance ทุกแบบ
- ไม่ได้รับรองคำถามที่อยู่นอก intent families ใน contracts
- Hybrid Router รองรับเฉพาะ intent families ที่ Skill catalogs ประกาศไว้
- semantic routing มีความไม่คงที่ จึงต้องวัดซ้ำด้วย router fingerprint เดียวกัน
- ไม่ได้รับรอง causal inference หรือการตัดสินใจรายบุคคล
- การผ่าน frozen suite ไม่เท่ากับ production readiness
- general fallback path ยังมีความไม่แน่นอนจาก LLM และควรประเมินแยก

Frozen-v1 legacy baseline ยืนยันข้อจำกัดของ keyword selector:
paraphrase recall `55%`, boundary accuracy `95%` และ false match `5%`
ขณะที่ contracts ที่ route ถูกผ่าน live MCP `11/11` สามรอบด้วย evidence hash
เดียวกัน ดู
[Unseen Paraphrase + Boundary Baseline](../../artifacts/unseen_boundary_baseline_report.md)

หลัง audit พบว่า frozen-v1 มี ground-truth defects 5 จุด จึงเก็บไฟล์เดิมไว้เพื่อ
audit และสร้าง overlay `semantic-v2` ต่อมา typed contract audit พบว่า performance
coverage contract กำหนด `review_period=2023` จึงออก `semantic-v3` เป็น suite
ปัจจุบัน ห้ามเปรียบเทียบ score ข้าม suite version โดยไม่ระบุให้ชัด รายละเอียดอยู่ที่
[Evaluation README](../../tests/evaluation/README.md)

Final sequential acceptance runs ที่มี fingerprint เดียวกัน
(`hybrid-contract-router-v3`, `openai/gpt-oss-120b`) ได้ paraphrase `20/20`
และ boundary `20/20` ทั้งสองรอบ โดยไม่มี false match และ decision
projection SHA-256 เดียวกันที่
`e4b45b61f53ce754374629939f202567ced3f0bb3a9b5f90b66829ba57e3e50a`;
gate source SHA-256 คือ
`611aa9d67bddfe7405df36bc61ba63aa71599f13976a742c2d6cccb116eefcab`
และ catalog SHA-256 คือ
`ed3112d6292f38d4d51d068895a6659233f6b75c8d0a342607183f1a018c4377`;
run 1 ตรวจ live MCP ครบ `20/20`
contracts และได้คำตอบไม่ว่าง `20/20` ดู
[acceptance report](../../artifacts/v3_semantic_router_acceptance_report.md)
รวมถึง Agent E2E คำถามนับพนักงานที่ยังปฏิบัติงานแยกตามแผนก
ที่ route แบบ semantic เข้า `active_headcount_by_department`, รัน
`grouped_active_headcount` และได้ 25 คนครบ 8 แผนกตาม accepted evidence

V2 Incident Replay Suite freeze failure ที่เคยพบจริง 17 incidents หลังแก้
staffing-route regression ผ่าน live run สองรอบติดต่อกันที่ `17/17`, routing
`40/40` และ contracts `6/6` ต่อรอบ ดู
[incident report](../../artifacts/v2_incident_replay_report.md)

หลักที่ใช้ตีความผลคือ:

> Observation อย่างเดียวจำเป็นแต่ไม่เพียงพอ
> bounded-domain Skill ให้ semantics, contract ให้เกณฑ์ที่ตรวจได้ และ Claim
> Gate บังคับไม่ให้คำตอบเกิน accepted evidence

## ทดสอบ

```bash
python -m pytest tests --ignore=tests/test_lab8_planner.py -q
python -m unittest -v tests.test_lab8_planner
python scripts/replay_v2_incidents.py --progress
```

ผลทดสอบ local ล่าสุด: non-Lab 8 `117 passed` + 35 subtests;
Lab 8 แยก `2 passed`

รัน routing suite ค่าเริ่มต้น:

```bash
make evaluate-routing
```

ไฟล์ทดสอบสำคัญ:

- `tests/test_lab6_phase2b.py`
- `tests/test_lab6_atomic_grader.py`
- `tests/test_hr_skill_contracts.py`
- `tests/test_finance_skill_contracts.py`
- `tests/test_contract_router.py`

## ประวัติและจุดย้อนกลับ

เอกสารผลทดลอง Phase 1–2D เดิมยังอยู่ใน `artifacts/` เพื่อให้ตรวจย้อนกลับได้
แต่ไม่ใช่คำอธิบาย runtime ปัจจุบัน

v3 ต่อ history จาก v2 commit `f33546a` และมี tag
`v2-baseline-f33546a` สำหรับตรวจ baseline ก่อน Hybrid Router จุดอ้างอิง
ที่เก่ากว่านั้นอยู่ใน v2:

- [`49f6f10`](https://github.com/aekanun2020/v2-Python-Agent-LangGraph/tree/49f6f10)
  — original baseline ก่อนงาน Observation/Evidence/Skill
- [`7e24c20`](https://github.com/aekanun2020/v2-Python-Agent-LangGraph/tree/7e24c20)
  — HR/Finance Skill-contract milestone

เปิด baseline โดยไม่แก้ `main`:

```bash
git switch -c inspect-v2-baseline v2-baseline-f33546a
```

# V2 Incident Replay Suite — v3 Result

วันที่ทดสอบ: 2026-08-01 (Asia/Bangkok)

## ข้อสรุป

นำ failure ที่พบจริงระหว่างพัฒนา v2 จำนวน 17 incident มาทำเป็น manifest
แบบ versioned แล้ว replay กับ v3 ทั้งระดับ source architecture, unit behavior,
semantic routing, executable contracts และ live MSSQL MCP

ผลหลังแก้ regression ที่พบระหว่างรอบแรก:

- offline replay: `17/17`
- live run 2: incidents `17/17`, routing attempts `40/40`, contracts `6/6`
- live run 3: incidents `17/17`, routing attempts `40/40`, contracts `6/6`
- decision projection SHA-256 ของ run 2 และ run 3 ตรงกัน:
  `3a00e1644d7ec5fcd371c280a9d3145896b104178b469906b0e48a7a3d123fc0`
- normalized live contract evidence SHA-256 ของทั้งสาม live runs ตรงกัน:
  `7433847f7dcb26749004aa5cacecfd10f97352aa721945d208d46c2b46757648`

สอง incident ของ Planner เดิมถูกจัดเป็น `not_applicable_by_removal` ไม่ใช่
`fixed`: v3 ไม่มี `agent_planner.py`, `PlannerState`, `plan_write` หรือ
`plan_revise` จึงไม่มี execution path เดิมให้ replay

## Incident coverage

| Layer | Failure ที่ replay |
|---|---|
| Planner protocol | dict step `.lower()` crash, plan ordering/revision/in-progress rejection |
| Provider | `tool_choice=required` incompatibility, wrapped/control-character JSON |
| Control state | repeated action/result, repeated error, call budget, hard deadline |
| MCP recovery | transient 503 retry และ permanent 400 no-retry |
| Final gate | `None`/empty answer, unsupported recommendation, currency และ qualitative relabelling |
| Evidence contract | wrong Unicode filter, wrong distinct grain, incomplete max-only query |
| HR semantics | canonical headcount labels, review coverage, certification semantics, concentration, efficiency trap, staffing decision |
| Finance semantics | employment length/approval และ `loan_status`/approval confusion |
| Routing constraints | negation, population, comparison operator, top-N และ bucket boundaries |

รายการเต็มและ expected disposition อยู่ใน
[`tests/evaluation/v2_incidents.json`](../tests/evaluation/v2_incidents.json)

## Regression ที่ suite พบ

Live run 1 ก่อนแก้ได้ incidents `16/17`, routing `36/40`, contracts `6/6`.
คำถาม staffing decision:

> จากจำนวนกำลังคน ช่วยบอกว่าแผนกไหนควรเพิ่มหรือลดอัตรากำลัง

route ได้เพียง `1/5` ครั้ง เพราะ LLM บางรอบส่ง exact quote เดียวเพื่อพิสูจน์
สอง routing concepts และ deterministic admission gate ปฏิเสธด้วย
`one evidence span cannot prove every routing concept`

ไม่ได้แก้ด้วยการผ่อน hard gate หรือเพิ่ม retry ให้ LLM แต่เพิ่ม
Skill-owned high-precision `lexical_pattern_groups` ที่ต้องพบพร้อมกันทั้ง:

1. คำขอเพิ่ม/ลดคนหรืออัตรากำลัง
2. headcount, จำนวนกำลังคน, project value หรือมูลค่าโครงการ/งานที่ใช้เป็นฐาน

หลังแก้ route นี้เป็น lexical โดยไม่เรียก semantic model และ live run 2–3
ผ่านทุกครั้ง ขณะที่ near-boundary suite เดิมยังผ่าน `20/20`

## Non-regression ของ acceptance suite เดิม

หลัง catalog เปลี่ยน ได้ regenerate `semantic-v3` acceptance สองรอบ:

| Run | Paraphrases | Boundaries | False matches | Lexical | Semantic | Attempts | Abstain |
|---|---:|---:|---:|---:|---:|---:|---:|
| Acceptance 1 | 20/20 | 20/20 | 0 | 14 | 7 | 26 | 19 |
| Acceptance 2 | 20/20 | 20/20 | 0 | 14 | 7 | 26 | 19 |

decision projection SHA-256 ของ acceptance ทั้งสองรอบตรงกัน:
`e4b45b61f53ce754374629939f202567ced3f0bb3a9b5f90b66829ba57e3e50a`

Acceptance run 1 ผ่าน live MCP contracts `20/20`, non-empty answers `20/20`
และ evidence SHA-256 เดิม
`e4471a2337e3fe8df765ec446789c2a6bf5529d1a42c0289b0664ca7ae92ab91`

## วิธีรัน

Offline:

```bash
python scripts/replay_v2_incidents.py \
  --progress \
  --output artifacts/v2_incident_replay_offline.json
```

Live routing ห้ารอบต่อ incident พร้อม MCP contract replay:

```bash
ROUTER_MODEL=openai/gpt-oss-120b \
python scripts/replay_v2_incidents.py \
  --live --repeat 5 --progress \
  --output artifacts/v2_incident_replay_live.json
```

Artifacts ที่เก็บไว้:

- `v2_incident_replay_offline.json`
- `v2_incident_replay_live_run1.json` — pre-fix regression evidence
- `v2_incident_replay_live_run2.json` — post-fix pass
- `v2_incident_replay_live_run3.json` — post-fix repeated pass

## ขอบเขตของข้อสรุป

ผลนี้รองรับเฉพาะ 17 incidents ที่ถูก freeze ใน manifest และ TestDB/MCP state
ของรอบทดสอบ ไม่ได้รับรอง arbitrary long-context conversation, provider outage
ทุกแบบ, schema ใหม่ หรือ intent นอก HR/Finance Skills การเพิ่ม incident ใหม่ต้อง
เพิ่ม fixture แยก ไม่แก้ expected result ย้อนหลังโดยไม่มี version ใหม่

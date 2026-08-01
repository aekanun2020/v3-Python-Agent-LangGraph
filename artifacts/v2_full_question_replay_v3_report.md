# V2 Full Question Replay on V3

## คำถามที่การทดลองนี้ตอบ

> เมื่อนำคำถามภายนอกทั้งหมดที่เคยบันทึกไว้ใน versioned evaluation artifacts
> ของ v2 มารันกับ v3 ปัจจุบัน v3 ทำได้ครบและยึด tool context หรือไม่

คำตอบคือ **ยังไม่ครบทั้งหมด** ผล final adjusted replay ผ่าน **55/63 ข้อ
(87.3%)** เหลือ failure จริง 8 ข้อ การทดลองนี้จึงหักล้างคำกล่าวแบบกว้างว่า
“v3 ดีกว่า v2 ทุกมิติ” แต่ให้ baseline ที่ตรวจซ้ำและไล่สาเหตุได้สำหรับแก้รอบถัดไป

## ขอบเขตและ provenance

- v2 source commit: `f33546aea94620e1e27425d34517e76a9443a5c2`
- อ่านคำถามจาก versioned JSON ใน `artifacts/` และ `tests/evaluation/`
- ใช้ key `question`, `prompt`, `user_question` แล้ว deduplicate ข้อความตรงกัน
- รวมเฉพาะคำถามที่เคยส่งให้ agent ภายนอก ไม่รวมข้อความย่อยของ unit test
  ที่ใช้ทดสอบ parser/verifier ภายใน
- เพิ่ม manual-history 2 ข้อที่ตรวจย้อนกลับได้แต่ไม่อยู่ใน JSON: คำถามนับ
  active headcount จาก versioned README และคำถาม employment/approval จาก
  owner-supplied development transcript
- ได้คำถามไม่ซ้ำ 63 ข้อ; question projection SHA-256:
  `e90b98c24b5aa3836f8c2d05ff0f24eb1c2a453afc44d0edeba755d9c1602fb1`
- manifest ที่ freeze คำถามและ provenance:
  [`tests/evaluation/v2_full_question_replay.json`](../tests/evaluation/v2_full_question_replay.json)

มีการแก้ expected route เฉพาะ 5 ข้อที่ audit ภายหลังยืนยันว่า ground truth
เดิมบกพร่อง เช่น คำถามไม่ได้ระบุ constraint ครบแต่เดิมกลับคาดให้เข้า contract
การแก้นี้บันทึกเหตุผลรายข้อไว้ใน manifest ไม่ได้แก้ข้อความคำถาม

## วิธีทดสอบ

การรันใช้ OpenRouter และ MSSQL MCP จริง:

- Agent model: `qwen/qwen3.5-35b-a3b`
- Observer model: `openai/gpt-oss-120b`
- Router model: `openai/gpt-oss-120b`
- routing mode: `hybrid`
- contract case: route -> live MCP query -> contract completeness -> claims ->
  Context Fidelity
- general case: ตรวจว่า router abstain -> รัน Pure Python Agent จริง ->
  tool calls -> Observation/Claim Gate -> Context Fidelity

ไม่บันทึก API key หรือ MCP endpoint ลง artifact

รอบแรกจงใจใช้ budget 90 วินาทีเพื่อค้นหา stress failure จากนั้นแยก controlled
recheck ออกเป็น:

1. infrastructure recheck สำหรับ SSL EOF หนึ่งข้อ
2. default-budget recheck 240 วินาทีสำหรับ 10 ข้อที่ชน budget 90 วินาที
3. semantic-audit recheck หลังแก้ metric ให้ยอมรับการปัดทศนิยมแบบโปร่งใส

ผล final ใช้ผล recheck เฉพาะ case ที่ประกาศไว้แทนผลรอบแรก และเพิ่ม live run
ของ manual-history 2 ข้อ จึงไม่ซ่อน timeout
และไม่เอาปัญหา transport มาปนกับ accuracy failure นโยบาย merge และ source
artifact ทั้งหมดอยู่ใน final JSON

## ผล final adjusted

| มิติ | ผ่าน | ทั้งหมด | อัตรา |
|---|---:|---:|---:|
| คำถามรวม | 55 | 63 | 87.3% |
| Routing | 59 | 63 | 93.7% |
| Contract live path | 34 | 38 | 89.5% |
| General-agent live path | 21 | 25 | 84.0% |

| กลุ่มคำถาม | ผ่าน/ทั้งหมด |
|---|---:|
| Finance boundaries | 9/10 |
| Finance legacy general | 1/1 |
| Finance primary Q1-Q10 | 9/10 |
| Finance unseen paraphrases | 9/10 |
| HR boundaries | 9/10 |
| HR primary Q1-Q10 | 7/10 |
| HR unseen paraphrases | 10/10 |
| V2 manual history | 1/2 |

Decision projection SHA-256 ของ final result คือ
`e63218092f03e5b1a4bd13e19567b2573c415c51a97c45c682095220ab5cd757`

## 8 ข้อที่ยังไม่ผ่าน

### Routing mismatch — 4 ข้อ

1. `v2q_018` — เป้าหมาย expert skill record 50%: gate ไม่ผูกเลข 50%
   เข้ากับ contract constraint `expert_record_share_threshold`
2. `v2q_021` — employment extrema: router ตีความการขอทั้งค่าต่ำสุดรวม N/A
   และค่าต่ำสุดเมื่อไม่รวม N/A ว่าขัดกับ requirement ที่ต้องเก็บ N/A
3. `v2q_024` — training concentration 50%: gate ไม่ผูกเลข 50% เข้ากับ
   `training_hour_concentration_threshold`
4. `v2q_039` — review coverage: เลขข้อมูล 7 และ 25 ถูกมองเป็น unlisted
   fixed constraints แทน numerator/denominator ที่ผู้ใช้ให้มา

ทั้งสี่ข้อ abstain เข้า general path แทน contract ที่คาดไว้ จึงนับ routing fail
แม้ระบบยังอาจสร้างคำตอบบางส่วนได้

### General answer ขัดกับ tool context — 4 ข้อ

1. `v2q_008` — “funding_ratio คือ approval rate ใช่หรือไม่”: draft recovery
   หลัง Observer ไม่รับ claim กลับปล่อยตัวอย่างตัวเลข 100/90 และ 100/80
   ที่ไม่มี direct evidence
2. `v2q_015` — Charged Off strict dual condition: คำถามไม่ได้ระบุเงื่อนไข
   ที่สองให้ครบ จึงเข้า general path แต่คำตอบปล่อยตัวเลขที่ Context Fidelity
   รองรับเพียงบางส่วน (`numeric_precision=0.667`)
3. `v2q_030` — “นับพนักงานทั้งหมดแยกตามแผนก”: agent ใช้ผล active-only
   25 คนมาตอบคำว่า “ทั้งหมด” และเพิ่มสัดส่วน/คำตีความองค์กรที่ไม่มีหลักฐาน
   (`numeric_precision=0.889`)
4. `v2q_063` — “ระยะเวลาการทำงานที่มีผลต่อการอนุมัติวงเงิน”: router
   abstain ถูก แต่ general answer ยังอ้างความสัมพันธ์กับวงเงินและนำ Charged Off
   มาตีความเกินคำถาม/หลักฐาน (`numeric_precision=0.75`)

ปัญหาหลักของกลุ่มนี้ไม่ใช่การเรียก MCP ไม่สำเร็จ แต่เป็นช่วง
**verify-then-emit**: draft recovery ยังสามารถนำ claim ที่ Observer ไม่รับกลับมา
และ numeric verifier ยังตรวจว่าตัวเลข “ปรากฏใน evidence” มากกว่าตรวจว่า
ความสัมพันธ์เชิงความหมายของ claim ถูกต้อง

## ข้อสรุปที่อ้างได้และอ้างไม่ได้

อ้างได้:

- v3 รันคำถามประวัติ v2 ที่ค้นย้อนกลับได้ครบ 63 ข้อด้วย live tool path
- ภายใต้ configuration นี้ ผ่าน 55/63 และระบุ failure จริงได้ 8 ข้อ
- unseen HR paraphrases ผ่าน 10/10 แต่ HR primary ยังมี routing gap 3 ข้อ
- การแยก Skill/Contract/Observation/Claim Gate ช่วยหลายกรณี แต่ยังไม่รับรอง
  tool-context fidelity ของ general path

ยังอ้างไม่ได้:

- v3 ดีกว่า v2 ทุกมิติ
- v3 มี accuracy สูงกว่า v2 อย่างมีนัยสำคัญ เพราะรอบนี้ไม่ได้รัน v2 และ v3
  แบบ head-to-head ด้วย environment, model, budget และ scorer เดียวกัน
- 55/63 เป็น production reliability หรือครอบคลุมคำถาม HR/Finance ทุกชนิด

## วิธีทำซ้ำ

สร้าง inventory ใหม่จาก checkout ของ v2:

```bash
python scripts/build_v2_question_inventory.py \
  --v2-repo ../v2-Python-Agent-LangGraph \
  --output tests/evaluation/v2_full_question_replay.json
```

รันทั้ง suite (ต้องตั้ง `.env` สำหรับ OpenRouter และ MCP):

```bash
python scripts/replay_v2_questions.py \
  --manifest tests/evaluation/v2_full_question_replay.json \
  --output artifacts/v2_full_question_replay_v3_run.json
```

รันเฉพาะข้อ:

```bash
python scripts/replay_v2_questions.py --case-id v2q_030 \
  --output artifacts/v2q_030_recheck.json
```

ไฟล์ผล final ที่รวม controlled rechecks:
[v2_full_question_replay_v3_final.json](v2_full_question_replay_v3_final.json)

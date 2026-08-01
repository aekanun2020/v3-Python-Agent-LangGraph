# v3.1 Evidence-context accuracy report

วันที่ทดสอบ: 2026-08-01

## เป้าหมาย

เพิ่มความแม่นยำตาม context ที่ได้จาก tool โดยไม่เพิ่มกฎ safety เฉพาะโดเมน:

1. Python บันทึก `EvidenceFrame` ทันทีหลัง MCP call
2. LLM แปลความหมายได้ แต่เขียนทับ success, field และ canonical label จาก frame ไม่ได้
3. General path สร้าง Claim Ledger ก่อนทำงาน และเรียก Dynamic Observer เมื่อ claim
   ยังไม่ครบ แม้ Python จะไม่พบ semantic-risk keyword
4. Final answer ประกอบจาก verified claim allowlist; ไม่ดึงข้อความที่ Final Observer
   ตัดทิ้งกลับมาจาก draft
5. รายงาน Context Fidelity แยกตัวเลข label claim และ unsupported inference

## โครงสร้างที่ทดสอบ

```text
MCP Tool Result
      |
      v
EvidenceFrame (Python)
 success / result kind / fields / rows / SQL semantics / grain / labels / numbers
      |
      v
Deterministic Observation
      |
      +-- unresolved claim or semantic risk --> LLM Dynamic Observer
      |                                           |
      +-------------------------------------------+
                          |
                          v
                   accepted evidence
                          |
                          v
                    proposed answer
                          |
                          v
                    Final Observer
                          |
                          v
               verified claim allowlist
                          |
                          v
               Context Fidelity measurement
```

## Automated regression

| Suite | Result |
|---|---:|
| non-Lab 8 unit tests | 125/125 |
| Lab 8 tests | 2/2 |
| V2 Incident Replay (offline) | 17/17 |
| EvidenceFrame-specific tests | 6/6 |

Regression tests รวมกรณี LLM ส่ง `action_succeeded=false`, field ปลอม และ label
`การผลิต` แต่ Python ต้องยึดผล tool ว่า success, fields คือ
`department, employee_count` และ label คือ `ผลิต` เท่านั้น

## Live OpenRouter + MCP

ใช้โมเดล `openai/gpt-oss-120b` เป็น Agent, Router และ Observer เพื่อควบคุมตัวแปร
โมเดล และใช้ MSSQL MCP จริง โดยไม่บันทึก secret หรือ endpoint ลง artifact

### Case A — Skill/contract path

คำถาม: `นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก`

- semantic route: `active_headcount_by_department`, confidence 0.99
- MCP contract role: `grouped_active_headcount`
- คำตอบ: 25 คน ครบ 8 canonical department labels
- Context Fidelity: `supported`, frames 1/1, numeric precision 1.000,
  label recall 1.0, claim recall 1.0

### Case B — General path ที่ไม่มี Skill contract

คำถาม: `แสดงจำนวนใบรับรองแยกตามชื่อใบรับรอง`

- router abstain อย่างถูกต้องและส่งเข้า general path
- Claim Ledger มี 1 claim
- schema call: Dynamic Observer เลือก `query_more`
- aggregate query: Dynamic Observer พิสูจน์ `claim_001` และเลือก `accept`
- Final Observer ตัด business interpretation ที่ tool ไม่ได้พิสูจน์
- final output มีชื่อใบรับรอง 7 รายการ รายการละ count 1 โดยไม่ซ้ำ
- Context Fidelity: `supported`, frames 2/2, numeric precision 1.000
- MCP เกิด transient `RemoteProtocolError` หนึ่งครั้ง; transport retry สำเร็จและใช้
  เฉพาะผล query ที่สำเร็จเป็น accepted evidence

## Regression ที่ live test ค้นพบและแก้แล้ว

ก่อนแก้ Final Observer ระบุว่า business interpretation ไม่มีหลักฐาน แต่ Claim Gate
ยังดึงบรรทัดจาก Agent draft กลับมา ทำให้เกิดรายการซ้ำและประโยคว่าใบรับรองที่มีอย่างละ
1 รายการ “แสดงว่าทีมมีทักษะหลากหลาย”

หลังแก้ เมื่อ Observer allowlist ไม่ว่าง draft recovery ถูกปิด ผลลัพธ์จึงเหลือเฉพาะ
7 claims ที่ Observer อนุญาต Draft recovery ยังมีเฉพาะ fallback กรณี Observer
ส่ง allowlist ว่าง และทุกบรรทัดต้องผ่าน deterministic numeric/unit/grain checks

## ขอบเขตการรับรอง

ผลนี้พิสูจน์ว่า v3.1 รักษา tool context ดีกว่า commit ก่อนหน้าในมิติที่ตรวจได้:
success/error, field, SQL filter/group/aggregation, grain, exact label, number และ
verified claim emission พร้อมคง V2 incident regression 17/17

ยังไม่ใช่หลักฐานว่าเข้าใจทุก intent หรือ semantic claim ทุกภาษา Context Fidelity
เป็น post-condition ที่ตรวจสิ่งซึ่งทำให้เป็นโครงสร้างได้ ส่วน claim เชิงความหมายที่ไม่อยู่
ใน Skill/contract ยังต้องพึ่ง LLM Observer และควรขยาย unseen evaluation ต่อไป

# v3-Python-Agent-LangGraph

## Experimental typed-intent router (Full-63)

branch `codex/typed-intent-router` ได้รันคำถาม frozen เดิมครบ 63 ข้อกับ live
OpenRouter + MSSQL MCP แล้ว โดยไม่รวม latency ในคะแนน:

| รายการ | ผล |
|---|---:|
| Router implementation | `9bbe1de86a5db208be33faa22058fb6bab701840` |
| Replay binding fix | `1a573c40fbcbfa4d1cb505f01d894e2b9fea5c45` |
| Raw one-shot | `59/63` |
| Controlled adjusted automated | `63/63` |
| Semantic audited | **`62/63`** |
| Typed incidents Q018/Q021/Q024/Q039 | **`4/4`** |

ผลดิบที่ไม่ผ่านมี Q003/Q004 จาก budget/timeout และผ่านเมื่อ controlled
recheck ส่วน Q008/Q030 เป็น expected-route ของ frozen manifest ที่เก่ากว่า
contract ใหม่ ไม่ใช่คำตอบผิด อย่างไรก็ตาม Q027 เป็น automated false positive:
คำตอบบอกเพียงว่าทุกแผนกต่ำกว่า 80% แต่ไม่ได้รายงาน coverage รายแผนกตามที่ถาม
จึงยังอ้างความถูกต้องเชิงความหมายได้เพียง 62/63 และยังไม่ควร merge เข้า main
จนกว่าจะตัดสินใจว่าจะเพิ่ม department-grain contract สำหรับ Q027 หรือคงให้
general path รับผิดชอบ

รายละเอียด provenance, คำวินิจฉัยรายข้อ และ SHA-256 อยู่ใน
[Typed-intent Full-63 report](artifacts/typed_intent_router_full63_report.md)
และ [machine-readable baseline](artifacts/typed_intent_router_full63_baseline.json)
คำถามเต็มทั้ง 63 ข้อยังคงอยู่ในตารางด้านล่างและใน
[`tests/evaluation/v2_full_question_replay.json`](tests/evaluation/v2_full_question_replay.json)

## Latest verified baseline

ผลล่าสุดที่มี live OpenRouter + read-only MSSQL MCP evidence ครบชุด บันทึกเมื่อ
2026-08-02 และอ้างอิงด้วย tag `eval-v3-28ddb98-full63`:

| รายการ | ค่าที่รับรอง |
|---|---|
| V3 code under test | `28ddb9861b2b28fba51cddfacfe197a3ab145aea` (`28ddb98`) |
| V2 comparison baseline | `f33546aea94620e1e27425d34517e76a9443a5c2` (`f33546a`) |
| Frozen suite | V2 Full Question Replay, 63 คำถาม |
| V2 automated score | `47/63`; evidence-answer check `52/63` |
| V3 raw frozen-manifest score | `53/63` |
| V3 fair adjusted score | `57/63` หลัง controlled recheck และยอมรับ intentional contract routes |
| Accuracy-only hybrid oracle | `61/63` จาก semantic audit; เป็นเพดานย้อนหลัง ไม่ใช่ผล router ที่รันจริง |
| Models | Agent `qwen/qwen3.5-35b-a3b`; Router/Observer `openai/gpt-oss-120b` |

คะแนนไม่รวม latency และยังไม่รองรับคำกล่าวว่า v3 ดีกว่า v2 ทุกคำถาม:
v2 ยังดีกว่าใน Q018, Q021, Q024 และ Q039 ส่วน Q027 กับ Q063
ยังไม่น่าเชื่อถือในทั้งสอง runtime ตาม semantic audit

แหล่งตรวจสอบหลัก:

- [Machine-readable verified baseline](artifacts/latest_verified_baseline.json)
- [V2/V3 Full-63 head-to-head report](artifacts/v2_v3_full63_head_to_head_report.md)
- [V2 scored live result](artifacts/v2_runtime_full_63_scored.json)
- [V3 current live result](artifacts/v2_full_question_replay_v3_current_run.json)
- [V3 controlled recheck](artifacts/v2_full_question_replay_v3_current_recheck.json)
- [V3 current regression report](artifacts/v2_full_question_replay_v3_current_regression_report.md)

### Commit และผลที่นำมาเปรียบเทียบ

การเปรียบเทียบนี้รัน runtime จากสอง commit ต่อไปนี้โดยตรง ไม่ได้เปรียบเทียบ
commit ที่มีเฉพาะเอกสารหรือ artifacts:

```text
V2: f33546aea94620e1e27425d34517e76a9443a5c2
V3: 28ddb9861b2b28fba51cddfacfe197a3ab145aea
```

commit `6acce1d` มีหน้าที่บันทึก README, replay scripts และผลการทดลองเท่านั้น
จึงไม่ใช่ V3 runtime ที่อยู่ใต้การทดสอบ ผล automated รายข้อด้านล่างเป็นผลดิบ
ตาม frozen manifest เดียวกัน ส่วน `57/63` เป็นผลปรับอย่างเป็นธรรมหลัง
controlled recheck และ semantic audit ตามรายงาน ไม่ควรนำสองมุมนี้มาปนกัน

### สรุปว่า V3 ดีขึ้นหรือแย่ลงอย่างไร

**ภาพรวมดีขึ้น แต่ไม่ชนะทุกคำถาม** เมื่อเทียบ runtime commit ข้างต้น:

| มุมเปรียบเทียบ | V2 | V3 | ผลต่าง |
|---|---:|---:|---:|
| Raw automated | 47/63 (74.6%) | 53/63 (84.1%) | V3 +6 ข้อ (+9.5 จุดร้อยละ) |
| Fair adjusted | 47/63 (74.6%) | 57/63 (90.5%) | V3 +10 ข้อ (+15.9 จุดร้อยละ) |
| ผ่านทั้งคู่ใน raw run | 41 ข้อ | 41 ข้อ | เท่ากัน |
| ผ่านเฉพาะ V3 ใน raw run | — | 12 ข้อ | Q003, Q009, Q020, Q025, Q031, Q043, Q047, Q050, Q052, Q054, Q057, Q062 |
| ผ่านเฉพาะ V2 ใน raw run | 6 ข้อ | — | Q008, Q018, Q021, Q024, Q030, Q041 |
| ไม่ผ่านทั้งคู่ใน raw run | 4 ข้อ | 4 ข้อ | Q027, Q039, Q059, Q063 |

Raw score เพียงอย่างเดียวสรุป semantic correctness ไม่ได้ หลังตรวจคำตอบกับ
tool context และ controlled recheck พบภาพที่แม่นกว่าดังนี้:

- **V3 ดีขึ้นชัดเจน** ใน Q008, Q015 และ Q030 เพราะแยก semantic identity,
  หยุดคำขอที่ให้เงื่อนไขไม่ครบ และรักษา population/label ตาม evidence ได้ดีขึ้น
  ส่วน Q059 คำตอบ V3 ถูกต้องแต่ scorer นับ user-supplied threshold เป็น
  unsupported number จึงเป็น false negative
- **V2 ยังดีกว่า V3** ใน Q018, Q021, Q024 และ Q039 เพราะ V3 typed router
  เข้มเกินไปและ abstain ก่อนเข้า deterministic contract executor ทั้งที่โจทย์
  มีข้อมูลพอ ปัญหาคือ threshold paraphrase, เงื่อนไขรวม/ไม่รวม N/A และการแยก
  ตัวเลข operand ออกจาก fixed constraint
- **ทั้งสองยังไม่น่าเชื่อถือ** ใน Q027 ซึ่งต้องรักษา grain ระดับแผนก และ Q063
  ซึ่ง schema ไม่มี approval decision แต่ agent ยังเสี่ยงตีความสถานะหลังปล่อยกู้
  เป็นการอนุมัติ
- จึงสรุปได้ว่า V3 เพิ่มความแม่นยำโดยรวมและลด semantic relabelling หลายกรณี
  แต่แลกกับ recall regression ของ valid analytical contracts 4 ข้อ

ค่า `61/63` เป็นเพดานย้อนหลังเมื่อเลือกคำตอบที่ดีกว่าระหว่าง V2/V3 รายข้อ
ไม่ใช่คะแนนของ router ที่สร้างและรันจริง จึงห้ามใช้เป็น production score

<details>
<summary><strong>คำถามเต็มทั้ง 63 ข้อและผล automated รายข้อของ V2/V3</strong></summary>

| ID | คำถามเต็ม | V2 automated | V3 raw automated |
|---|---|---:|---:|
| Q001 | Charged Off ทั้งพอร์ตมีกี่รายการ | ผ่าน | ผ่าน |
| Q002 | Joint App มีวงเงินเฉลี่ยเท่าไร | ผ่าน | ผ่าน |
| Q003 | annual_inc ของ Joint App แบ่งตามช่วงรายได้ | ไม่ผ่าน | ผ่าน |
| Q004 | application_type แบบ Individual กับ Joint App มีสัดส่วนจำนวนรายการในพอร์ตร้อยละเท่าไร | ผ่าน | ผ่าน |
| Q005 | certificate_obtained พิสูจน์ได้หรือไม่ว่า certification ยัง valid และใช้ได้ | ผ่าน | ผ่าน |
| Q006 | certification แต่ละชนิดมีผู้ถือกี่คน | ผ่าน | ผ่าน |
| Q007 | emp_length ของผู้กู้รายนี้คืออะไร | ผ่าน | ผ่าน |
| Q008 | funding_ratio คือ approval rate ใช่หรือไม่ | ผ่าน | ไม่ผ่าน |
| Q009 | home_ownership ใดทำให้ dti สูงขึ้น | ไม่ผ่าน | ผ่าน |
| Q010 | loan_amnt สูงสุดหนึ่งรายการคือเท่าไร | ผ่าน | ผ่าน |
| Q011 | training_type ใดมี concentration ของชั่วโมงอบรมเกิน 50% ของทั้งหมด | ผ่าน | ผ่าน |
| Q012 | กระจายจำนวนและสัดส่วนสินเชื่อตาม loan_status ทุกสถานะอย่างไร ห้ามตีความ loan_status เป็นผลการอนุมัติ | ผ่าน | ผ่าน |
| Q013 | กลุ่ม emp_length ใดมีทั้ง int_rate เฉลี่ยสูงกว่าค่าเฉลี่ยทั้งพอร์ต และสัดส่วน Charged Off สูงกว่าค่าเฉลี่ยทั้งพอร์ต โดยใช้เงื่อนไขมากกว่าแบบ strict รายงาน benchmark และทุกกลุ่มที่ผ่าน ห้ามใช้เป็น causal model หรือคำตัดสินรายบุคคล | ผ่าน | ผ่าน |
| Q014 | ควรลดคนหรือเพิ่มคนจาก headcount เพียงอย่างเดียวหรือไม่ | ผ่าน | ผ่าน |
| Q015 | คัดช่วงอายุงานที่สัดส่วน Charged Off สูงกว่าค่าเฉลี่ยรวมแบบ strict และผ่านทั้งสองเงื่อนไข | ผ่าน | ผ่าน |
| Q016 | ค่า dti เฉลี่ยทั้งพอร์ตเป็นเท่าไร | ผ่าน | ผ่าน |
| Q017 | จาก headcount, employment type, performance reviews, training, skills, certifications และ project value จงเลือกหนึ่งแผนกที่ควรลดคน และหนึ่งแผนกที่ควรเพิ่มคน พร้อมเหตุผลเชิงธุรกิจ | ผ่าน | ผ่าน |
| Q018 | จาก skill records ทั้งหมด จงวิเคราะห์สัดส่วนระดับ `เชี่ยวชาญ` และตรวจว่าสูงถึงเป้าหมาย 50% หรือไม่ พร้อมแยกตาม `skill_category` | ผ่าน | ไม่ผ่าน |
| Q019 | จากข้อมูลพบว่า `วิจัยและพัฒนา` มีพนักงานปฏิบัติงาน 3 คน และมีโครงการมูลค่า 10,000,000 ส่วน `เทคโนโลยีสารสนเทศ` มีพนักงาน 5 คนและโครงการมูลค่า 5,000,000 จงสรุปว่าแผนกใดใช้กำลังคนมีประสิทธิภาพกว่ากัน | ผ่าน | ผ่าน |
| Q020 | จากจำนวนกำลังคนกับมูลค่างาน ช่วยบอกว่าฝ่ายไหนควรรับเพิ่มหรือลดอัตรากำลัง | ไม่ผ่าน | ผ่าน |
| Q021 | จำแนกตาม emp_length แล้ว กลุ่มใดมี funded_amnt เฉลี่ยสูงสุดและต่ำสุด รายงานจำนวน int_rate เฉลี่ย และ dti เฉลี่ยของกลุ่มดังกล่าว พร้อมระบุกลุ่มต่ำสุดเมื่อไม่รวม N/A | ผ่าน | ไม่ผ่าน |
| Q022 | จำแนกตาม home_ownership ทุก label แล้ว รายงานจำนวนรายการ funded_amnt เฉลี่ย int_rate เฉลี่ย และ dti เฉลี่ย ห้ามตัดกลุ่มขนาดเล็กออก | ผ่าน | ผ่าน |
| Q023 | จำแนกทุกกลุ่ม home_ownership แล้วรายงาน funded_amnt, int_rate และ dti | ผ่าน | ผ่าน |
| Q024 | ชั่วโมงอบรมของบริษัทกระจายตาม `training_type` อย่างไร และประเภทใดเกินนโยบาย concentration limit 50% ของชั่วโมงอบรมทั้งหมด | ผ่าน | ไม่ผ่าน |
| Q025 | ช่วงอายุงานใดได้ยอดจัดสรรเฉลี่ยมากที่สุดและน้อยที่สุด โดยแสดงค่าที่ไม่ระบุด้วย | ไม่ผ่าน | ผ่าน |
| Q026 | ช่วยแจกแจงจำนวนคนที่มีสถานะปฏิบัติงาน แยกตาม department | ผ่าน | ผ่าน |
| Q027 | ตรวจ performance review coverage รายฝ่ายเทียบเกณฑ์ 80% | ไม่ผ่าน | ไม่ผ่าน |
| Q028 | ทุกรายการอบรมมี `certificate_obtained = True` หรือไม่ และข้อมูลนี้พิสูจน์ได้หรือไม่ว่าพนักงานทุกคนมี certification ที่ยังใช้ได้ | ผ่าน | ผ่าน |
| Q029 | นับจำนวนหลักสูตรอบรมแยกตาม training_type | ผ่าน | ผ่าน |
| Q030 | นับพนักงานทั้งหมดแยกตามแผนก | ผ่าน | ไม่ผ่าน |
| Q031 | นับพนักงานที่ลาออกแล้วแยกตาม department | ไม่ผ่าน | ผ่าน |
| Q032 | บริษัทกำหนดว่า project portfolio มี concentration risk หากโครงการมูลค่าสูงสุดสองอันดับรวมกันเกิน 60% ของมูลค่าทุกโครงการ จงตรวจตามนโยบายนี้ | ผ่าน | ผ่าน |
| Q033 | บริษัทกำหนดว่าแผนกมีความเสี่ยงด้าน contract dependency เมื่อพนักงานสัญญามากกว่า 50% ของพนักงานที่ปฏิบัติงานในแผนก แผนกใดเข้าเกณฑ์ แสดง numerator, denominator และอัตราร้อยละ | ผ่าน | ผ่าน |
| Q034 | พนักงานคนใดควรได้เลื่อนตำแหน่งจาก skill_category | ผ่าน | ผ่าน |
| Q035 | พนักงานที่มีสถานะ `ปฏิบัติงาน` มีทั้งหมดกี่คน และแยกตามค่า `department` ในฐานข้อมูลอย่างไร | ผ่าน | ผ่าน |
| Q036 | พนักงานที่ยังทำงานอยู่มีทั้งหมดกี่คน | ผ่าน | ผ่าน |
| Q037 | พอร์ตสินเชื่อทั้งหมดมีกี่รายการ ยอดวงเงินที่ขอ loan_amnt และยอดที่ได้รับ funding funded_amnt รวมเท่าใด และค่าเฉลี่ยต่อรายการเท่าใด ห้ามระบุสกุลเงินถ้าไม่มี metadata | ผ่าน | ผ่าน |
| Q038 | ภายใต้เกณฑ์ contract dependency มากกว่า 50% สำหรับคนปฏิบัติงาน แผนกใดเข้าเกณฑ์ | ผ่าน | ผ่าน |
| Q039 | มีพนักงานที่ปฏิบัติงาน 25 คน แต่มี performance review ปี 2023 จำนวน 7 รายการ ก่อนเปรียบเทียบผลงานระหว่างแผนก จงคำนวณ evidence coverage และประเมินว่าผ่านเกณฑ์ขั้นต่ำ 80% หรือไม่ | ไม่ผ่าน | ไม่ผ่าน |
| Q040 | มีแผนกใดไม่มีพนักงานปฏิบัติงานเลย | ผ่าน | ผ่าน |
| Q041 | ยอด funded_amnt ของปี 2020 เท่าไร | ผ่าน | ไม่ผ่าน |
| Q042 | รายปี 2016 ถึง 2019 ใน issue_d_dim.year สรุป funded_amnt และ int_rate | ผ่าน | ผ่าน |
| Q043 | ลูกค้าที่มี loan_status Charged Off ควรถูกปฏิเสธครั้งต่อไปหรือไม่ | ไม่ผ่าน | ผ่าน |
| Q044 | สรุปพอร์ตทั้งหมดทั้งยอดรวมและค่าเฉลี่ยของ loan_amnt กับ funded_amnt | ผ่าน | ผ่าน |
| Q045 | สัดส่วนจำนวนรายการระหว่าง application_type แบบ Individual และ Joint App เป็นเท่าใด รายงานทั้งจำนวนและร้อยละของพอร์ตทั้งหมด โดยคง label ตามฐานข้อมูล | ผ่าน | ผ่าน |
| Q046 | สำหรับ application_type = Individual ที่ annual_inc ไม่เป็น NULL ให้แบ่ง fixed income band เป็น <50000, 50000-<70000, 70000-<100000 และ 100000+ แล้วรายงานจำนวน ช่วงรายได้ funded_amnt เฉลี่ย int_rate เฉลี่ย และ dti เฉลี่ยของทุก band | ผ่าน | ผ่าน |
| Q047 | สำหรับ application_type = Individual ที่ annual_inc ไม่เป็น NULL ให้ใช้ NTILE(4) เรียง annual_inc แบ่ง income quartile แล้วรายงานจำนวน ช่วงรายได้ funded_amnt เฉลี่ย int_rate เฉลี่ย และ dti เฉลี่ยของแต่ละ quartile | ไม่ผ่าน | ผ่าน |
| Q048 | สำหรับพนักงานสถานะ `ปฏิบัติงาน` จงแสดงจำนวนพนักงาน `ประจำ` และ `สัญญา` ของแต่ละแผนก พร้อมคำนวณสัดส่วนพนักงานสัญญาต่อจำนวนพนักงานของแผนก | ผ่าน | ผ่าน |
| Q049 | สำหรับสถานะปฏิบัติงาน แต่ละแผนกมีพนักงานประจำและสัญญาเป็นสัดส่วนเท่าไร | ผ่าน | ผ่าน |
| Q050 | หมวดทักษะใดมีสัดส่วนระเบียนระดับเชี่ยวชาญเกินครึ่งหนึ่ง | ไม่ผ่าน | ผ่าน |
| Q051 | เฉพาะผู้สมัครเดี่ยว แบ่งช่วงรายได้คงที่สี่ช่วงตั้งแต่ต่ำกว่า 50000 ถึง 100000 ขึ้นไป | ผ่าน | ผ่าน |
| Q052 | เปรียบเทียบ project value ต่อกำลังคนที่ยังทำงานอยู่รายฝ่าย แต่อย่าตีความเป็นผลิตภาพ | ไม่ผ่าน | ผ่าน |
| Q053 | แจกแจง loan_status ทุกสถานะ พร้อมจำนวนและสัดส่วนของแต่ละค่า | ผ่าน | ผ่าน |
| Q054 | แต่ละปี 2016-2019 จงหาส่วนต่างยอดที่ขอกับยอดที่จัดสรรและอัตราส่วนการจัดสรร | ไม่ผ่าน | ผ่าน |
| Q055 | แต่ละปี 2016-2019 มี requested_total จาก loan_amnt, funded_total จาก funded_amnt, funding_gap และ funding_ratio = SUM(funded_amnt)/SUM(loan_amnt) เท่าใด และห้ามสรุปว่าเป็น approval rate | ผ่าน | ผ่าน |
| Q056 | แบ่ง dti เป็น bucket <10, 10-<20, 20-<30, 30+ และ NULL แล้วรายงานจำนวน funded_amnt เฉลี่ย และ int_rate เฉลี่ยของทุก bucket พร้อมบอกแนวโน้มเชิงพรรณนาโดยห้ามอ้าง causality | ผ่าน | ผ่าน |
| Q057 | แบ่งภาระหนี้ต่อรายได้เป็นต่ำกว่า 10, 10 ถึงต่ำกว่า 20, 20 ถึงต่ำกว่า 30, ตั้งแต่ 30 และข้อมูลว่าง | ไม่ผ่าน | ผ่าน |
| Q058 | แผนกใดมีผลงานดีที่สุด | ผ่าน | ผ่าน |
| Q059 | โครงการสองรายการแรกกินสัดส่วนมูลค่ารวมเกินหกสิบเปอร์เซ็นต์หรือไม่ | ไม่ผ่าน | ไม่ผ่าน |
| Q060 | ใครบ้างที่มี performance review ล่าสุดต่ำกว่าเกณฑ์ | ผ่าน | ผ่าน |
| Q061 | ในแต่ละปี issue_d_dim.year มีจำนวนรายการ วงเงิน funded_amnt เฉลี่ย และ int_rate เฉลี่ยเท่าใด รายงานปี 2016 ถึง 2019 และแสดง int_rate เป็นร้อยละอย่างถูกต้อง | ผ่าน | ผ่าน |
| Q062 | นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก | ไม่ผ่าน | ผ่าน |
| Q063 | ระยะเวลาการทำงานที่มีผลต่อการอนุมัติวงเงิน | ไม่ผ่าน | ไม่ผ่าน |

</details>

ข้อควรอ่านร่วมกับตาราง: automated scorer ให้ false positive/false negative ได้
เช่น Q008 และ Q030 ดูเหมือน V3 ไม่ผ่านเพราะ frozen manifest ยังไม่รู้จัก
contract ใหม่ แต่ semantic audit พบว่า V3 ดีกว่า ส่วน Q039 แม้ automated
ไม่ผ่านทั้งคู่ แต่ V2 ให้คำตอบเชิงความหมายถูกกว่า รายละเอียด override ทั้งหมด
อยู่ใน [head-to-head report](artifacts/v2_v3_full63_head_to_head_report.md)

`git log -1` แสดง commit ล่าสุดของ branch ซึ่งอาจใหม่กว่ารุ่นที่ทดสอบแล้ว
เสมอ ให้ดู `code_under_test` ใน metadata หรือตรวจ tag ข้างต้นเมื่อต้องการ
ทราบว่าผลทดสอบรับรองโค้ด commit ใด หาก HEAD ใหม่กว่า `28ddb98` ต้องรัน
Full Replay ใหม่ก่อนเรียกว่า verified baseline ล่าสุด

## สถานะปัจจุบัน: Evidence-centric Pure Python Agent

งานพัฒนาล่าสุดอยู่ที่ **Lab 6** และไม่ใช้ LangGraph ใน critical path:

```text
Question
  -> explicit multi-condition completeness gate
  -> negation/schema-only request guard
  -> exact/high-precision lexical fast path
  -> entity/concept identity + polarity/operator + typed-constraint gate
  -> (เมื่อ lexical ไม่ชัด) semantic proposal 1 ครั้ง
  -> deterministic id/anchor/constraint/span gate
  -> Skill contract หรือ abstain เข้า general path

Skill contract -> MCP evidence -> deterministic checks -> Claim Gate -> Answer

General path  -> MCP tool call -> EvidenceFrame
              -> Python Observation
              -> quantitative risk? independent query + Python reconcile
              -> LLM Observer เมื่อ claim ยังไม่ครบ/เสี่ยงเชิงความหมาย
              -> verified claim allowlist -> Answer
              -> Context Fidelity measurement
```

เป้าหมายหลักคือ **ความแม่นยำตาม context ที่ได้จาก tool** ไม่ใช่การเพิ่ม
safety policy เฉพาะโดเมน Observation เพียงอย่างเดียวยังไม่พอ:

- **Router** เสนอ intent family แต่ไม่ได้มีอำนาจรับ evidence หรืออนุมัติคำตอบ
- **Requirement Gate** หยุดก่อนเรียก tool เมื่อผู้ใช้ประกาศจำนวนเกณฑ์ชัดเจน
  แต่ระบุเกณฑ์จริงไม่ครบ เช่นบอกว่ามีสองเงื่อนไขแต่ให้มาเพียงหนึ่ง
- **Skill** เก็บ semantics และ policy ของ bounded domain
- **Contract** นิยาม query, grain, field, label และ completion rule ที่ runtime ตรวจได้
- **Observation** ตรวจผล tool เทียบกับ state และ contract
- **Claim Gate** ปล่อยเฉพาะ claim ที่ accepted evidence รองรับ
- **EvidenceFrame** ล็อก field, row, filter, group, aggregation, label
  และตัวเลขจาก tool แบบ deterministic ก่อนให้ LLM ตีความ
- **Reconciliation** พักผล aggregate/join/ratio บน general path
  ไว้ก่อน แล้วขอ query อิสระที่ใช้ SQL shape ต่างกันแต่คืน
  output contract เดียวกัน; Python รับ evidence เมื่อ rows/values ตรงกันเท่านั้น
- **Context Fidelity** วัด numeric precision, exact-label recall,
  required-claim recall และประโยคอนุมานที่ไม่มีหลักฐาน

Runtime core ค้นหา contracts จาก
`skills/*/references/answer_contracts.json`; ไฟล์ generic
`labs/lab6_todo/executable_metric_contracts.json` ไม่มี HR/Finance contract
เพื่อไม่ให้ core ผูกกับโดเมนใดโดเมนหนึ่ง
ส่วนคำอธิบายที่ semantic router ใช้เสนอ candidate อยู่ใน
`skills/*/references/routing_catalog.json`

Skills ปัจจุบัน:

- [HR Analytics](skills/hr-analytics/SKILL.md)
- [Finance Analytics](skills/finance-analytics/SKILL.md)

### ผล controlled tests

| Suite | Repeated runs | Questions | Atomic items | Median |
|---|---:|---:|---:|---:|
| HR Skill | 2 | 10/10 | 77/77 | 0.706–0.710s |
| Finance Skill | 2 | 10/10 | 148/148 | 0.730–0.792s |

HR ทั้งสองรอบได้ answer hash เดียวกัน และ Finance non-regression หลังเพิ่ม HR
Skill ยังคง score และ answer hash เดิม ผลนี้วัดหลัง route เข้า contract ถูกแล้ว
ไม่ได้พิสูจน์ว่า selector แบบ substring เข้าใจ paraphrase

v3 จึงแยกความรับผิดชอบชัดเจน: ปฏิเสธคำขอแบบ negation/schema-only ก่อน,
รับ exact term หรือ Skill-declared high-precision lexical alias เมื่อได้ unique
contract และ typed constraints ครบโดยไม่เรียก Router LLM ถ้า lexical ไม่ชัดจึง
เรียก `ROUTER_MODEL` หนึ่งครั้ง แล้วให้ Python ตรวจ contract id, entity/metric
identity, concept evidence, anchor polarity, comparison operator,
contract-owned constraints, confidence และ exact spans ก่อนรับ route
ข้อความจาก router ไม่ใช่ accepted evidence

ผลนี้รับรองเฉพาะ intent families และชุดข้อมูลที่ contracts ประกาศไว้
ไม่ใช่การรับรองคำถาม HR/Finance ทุกแบบหรือ production readiness

อ่านรายละเอียดและวิธีรันที่
[Lab 6 — current architecture](labs/lab6_todo/README.md),
[v3 Hybrid Router acceptance report](artifacts/v3_semantic_router_acceptance_report.md),
[V2 Incident Replay report](artifacts/v2_incident_replay_report.md),
[V2 Full Question Replay on V3](artifacts/v2_full_question_replay_v3_report.md),
[V2/V3 three-question live recheck](artifacts/v2_v3_three_question_recheck_report.md),
[V2/V3 three-question recheck run 2](artifacts/v2_v3_three_question_recheck_run2_report.md),
[v3.1 Evidence-context report](artifacts/v3_1_evidence_context_report.md),
[HR report](artifacts/hr_skill_run4_run5_report.md) และ
[Finance report](artifacts/finance_skill_run3_run4_report.md)
และ [Three-question strict reconciliation report](artifacts/reconcile_three_question_live_run3_report.md)

### ผล Hybrid Router ล่าสุด

ทดสอบ `semantic-v3` แบบ sequential สองรอบด้วย
`openai/gpt-oss-120b` และ fingerprint เดียวกัน:

| Run | Paraphrases | Near-boundary | False matches | Routing median | Semantic median / p95 | Live MCP / answer |
|---|---:|---:|---:|---:|---:|---:|
| Acceptance 1 | 20/20 | 20/20 | 0 | 3.527605s | 4.726401s / 10.942734s | 20/20 / 20/20 |
| Acceptance 2 | 20/20 | 20/20 | 0 | 3.671955s | 4.467017s / 9.059617s | — |

ทั้งสองรอบมี lexical routes 14, semantic routes 7, semantic attempts 26 และ
abstentions 19 เท่ากัน decision projection SHA-256 ตรงกันที่
`e4b45b61f53ce754374629939f202567ced3f0bb3a9b5f90b66829ba57e3e50a`
fingerprint ระบุ gate source `611aa9d67bddfe7405df36bc61ba63aa71599f13976a742c2d6cccb116eefcab`
และ catalog `ed3112d6292f38d4d51d068895a6659233f6b75c8d0a342607183f1a018c4377`
ดูรายละเอียด suite history, live evidence และข้อจำกัดใน
[acceptance report](artifacts/v3_semantic_router_acceptance_report.md)

V2 Incident Replay หลังแก้ regression ผ่านสอง live runs ติดต่อกัน:
incidents `17/17`, routing attempts `40/40` และ contracts `6/6` ต่อรอบ
ดู [incident report](artifacts/v2_incident_replay_report.md)

การขยายจาก incident fixtures ไปยังคำถามภายนอกที่ค้นพบใน versioned v2
artifacts รวมกับ manual-history ที่ตรวจย้อนกลับได้มี 63 ข้อ baseline เดิมได้
`55/63` ส่วน verified run ปัจจุบันของ commit `28ddb98` ได้ raw `53/63`
และ fair adjusted `57/63` หลัง controlled recheck ผล v2 runtime จริงที่ commit
`f33546a` ได้ `47/63` ด้วย automated score เดียวกัน ผลนี้จึง **ยังไม่รองรับ**
คำกล่าวว่า v3 ดีกว่า v2 ทุกคำถาม ดูวิธีคัดคำถาม, scoring caveat และ semantic
audit ใน [head-to-head report](artifacts/v2_v3_full63_head_to_head_report.md)

## Quick start สำหรับผู้เรียน

พัฒนาและทดสอบด้วย Python 3.11:

```bash
conda create -n agentic-ai python=3.11 -y
conda activate agentic-ai
pip install -r requirements.txt
cp .env.example .env
```

แก้ `.env` แล้วใส่ค่าของตนเอง ห้าม commit คีย์จริง:

```dotenv
OPENROUTER_API_KEY=ใส่คีย์ของผู้เรียน
OPENROUTER_MODEL=qwen/qwen3.5-35b-a3b
OBSERVER_MODEL=openai/gpt-oss-120b
ROUTER_MODEL=openai/gpt-oss-120b
ROUTER_TIMEOUT_SECONDS=30
MCP_SERVER_URL=https://your-mcp-server.example/mcp
```

รัน Pure Python Agent ปัจจุบันกับ MCP:

```bash
python labs/lab6_todo/agent_todo.py \
  "นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก"
```

live E2E รอบสุดท้าย route คำถามนี้แบบ semantic เข้า
`active_headcount_by_department`, พบ MCP tools 5 ตัว, รัน role
`grouped_active_headcount` และจบด้วย terminal approval ที่ 25 คน
ครบ 8 แผนกตาม accepted evidence

`--contract-routing hybrid` เป็นค่าเริ่มต้น; ใช้ `--contract-routing lexical`
เมื่อต้องการเปรียบเทียบกับ selector แบบ literal เดิม

รัน automated tests:

```bash
python -m pytest tests --ignore=tests/test_lab8_planner.py -q
python -m unittest -v tests.test_lab8_planner
```

ผลทดสอบ local ล่าสุด: non-Lab 8 `149 passed` และ `52 subtests passed`;
Lab 8 แยก `2 passed`
ผล live general-path Reconciliation ดูที่
[Reconcile-first acceptance report](artifacts/reconciliation_first_report.md)

รัน routing acceptance ค่าเริ่มต้น (`semantic-v3`, hybrid, fail on error):

```bash
make evaluate-routing
```

### จุดย้อนกลับ

ประวัติ `main` ของ v3 ต่อจาก v2 commit `f33546a` และมี tag
`v2-baseline-f33546a` สำหรับย้อนกลับก่อนเพิ่ม Hybrid Router ส่วนจุดเก่ากว่านั้น
ดูได้ใน [v2 repository](https://github.com/aekanun2020/v2-Python-Agent-LangGraph):

- [`49f6f10`](https://github.com/aekanun2020/v2-Python-Agent-LangGraph/tree/49f6f10) — original baseline
- [`7e24c20`](https://github.com/aekanun2020/v2-Python-Agent-LangGraph/tree/7e24c20) — HR/Finance Skill milestone

ย้อน Hybrid Router โดยไม่แก้ `main` ได้ด้วย:

```bash
git switch -c inspect-v2-baseline v2-baseline-f33546a
```

> หลักสูตร **Agentic AI Development with Python (หลักสูตรที่ 2)** —
> เขียน Agent ด้วย Pure Python ทีละขั้น (Lab 1–7) แล้วเปรียบเทียบกับ LangGraph (Lab 8) ก่อน deploy เป็น API Service (Lab 9)

repo นี้เป็นชุดแล็บ **9 Lab** ที่ต่อเนื่องกัน สอนตั้งแต่เรียก LLM ครั้งแรก จนถึง deploy Agent เป็น API + Docker
ทุก Lab เชื่อมกับ **MCP MSSQL Server จริง** ของหลักสูตรที่ 1 เป็นแกนข้อมูลเดียวกัน

---

## เอกสารในโปรเจกต์นี้ต่างกันอย่างไร (อ่านไฟล์ไหนก่อน)

repo นี้มี README หลายระดับ แต่ละไฟล์ตอบคนละคำถาม — เลือกอ่านตามว่าคุณอยากรู้อะไร:

| ไฟล์ | ตอบคำถามว่า | เหมาะกับใคร |
| --- | --- | --- |
| **`README.md` (ไฟล์นี้)** | "โปรเจกต์นี้คืออะไร โครงสร้าง repo เป็นแบบไหน จะเริ่มอ่านที่ไหน" — ภาพรวมระดับ repo + จุดเริ่มต้น | คนเปิด repo ครั้งแรก |
| [`labs/README.md`](labs/README.md) | "หลักสูตรมีกี่ Lab เรียงยังไง **เส้นทางการเรียนรู้** ไล่จาก Lab 1 ถึง 9 อย่างไร ติดตั้ง/รันยังไง" — สารบัญ + เส้นเรื่องการสอน + setup/run | ผู้เรียน/ผู้สอนที่จะเดินตามหลักสูตร |
| `labs/labN_*/README.md` | "Lab นี้มีจุดประสงค์อะไร รันยังไง โค้ดจุดสำคัญอยู่ตรงไหน" — รายละเอียดเชิงลึกราย Lab | คนที่กำลังทำ Lab นั้นอยู่ |

> สรุปสั้น: **ไฟล์นี้ = ประตูหน้าระดับ repo** (โครงสร้าง + ชี้ทาง) · **`labs/README.md` = สารบัญ + เส้นเรื่องหลักสูตร + setup/run** · **README ราย Lab = คู่มือลงมือทำของแต่ละ Lab**

---

## เริ่มต้น (Clone Repository)

```bash
git clone https://github.com/aekanun2020/v3-Python-Agent-LangGraph.git
cd v3-Python-Agent-LangGraph
```

> **ขั้นตอนติดตั้งสภาพแวดล้อม (conda env + `.env` + dependencies) และวิธีรันแต่ละ Lab อยู่ใน [`labs/README.md`](labs/README.md)** — โดย Setup เต็มเป็นแหล่งเดียว (single source) อยู่ที่ [Lab 1](labs/lab1_setup/README.md) ทำครั้งเดียวก่อนเริ่มทุก Lab (พัฒนา/ทดสอบด้วย **Miniconda**, Python 3.11)

---

## โครงสร้างโปรเจกต์

```
v3-Python-Agent-LangGraph/
├── README.md                   # ไฟล์นี้ — ภาพรวมระดับ repo + ชี้ทาง
├── labs/
│   ├── README.md               # สารบัญ Lab 1–9 + เส้นทางการเรียนรู้ + setup/run
│   ├── core/                   # โค้ดกลางที่ทุก Lab ใช้ร่วมกัน (config/llm/mcp_client/registry)
│   ├── lab1_setup/             # Lab 1: ตรวจสภาพแวดล้อม (เจ้าของ Setup เต็ม)
│   ├── lab2_llm/               # Lab 2: เรียก LLM + เทียบโมเดล
│   ├── lab3_agent_loop/        # Lab 3: agent loop แรก (Pure Python)
│   ├── lab4_mcp_agent/         # Lab 4: + MCP MSSQL จริง
│   ├── lab5_skills/            # Lab 5: + Skill routing (มีโฟลเดอร์ skills/)
│   ├── lab6_todo/              # Lab 6: Pure Python Observation/Evidence/Claim Gate
│   ├── lab7_memory/            # Lab 7: + Memory/Compaction/Note-taking
│   ├── lab8_langgraph/         # Lab 8: LangGraph Agent (pivot — เทียบ Pure Python)
│   └── lab9_deploy/            # Lab 9: ห่อ agent เป็น FastAPI API + Docker
├── skills/
│   ├── hr-analytics/           # HR semantics + executable answer contracts
│   └── finance-analytics/      # Finance semantics + executable answer contracts
├── docker-compose.yml          # Lab 9: service agent (ชี้ MCP MSSQL จริงผ่าน .env)
├── .dockerignore
├── discover_mssql.py           # ยูทิลิตี้ตรวจการเชื่อมต่อ + list tools/args schema
├── screenshots/labs/           # ภาพหน้าจอผลการรันทดสอบจริง (Lab 1–9)
│   ├── lab1_check_env.png ... lab7_memory.png
│   ├── lab8_01_mssql_discovery.png / lab8_02_agent_q1.png / lab8_03_agent_q2.png
│   ├── lab9_api_deploy.png
│   └── layer_coverage_matrix.png   # ตารางแมป layer สถาปัตยกรรม × Lab
├── requirements.txt
├── .env.example                # เทมเพลต env (ไม่มีคีย์จริง)
├── .gitignore
└── (README.md)
```

---

## สถาปัตยกรรม Agent: App → Agent → LLM + 8 Layers

เพื่อให้เข้าใจว่าแต่ละ Lab "กำลังสร้างชิ้นส่วนไหนของ Agent" repo นี้ยึดภาพสถาปัตยกรรมเดียวกันทั้งหลักสูตร
หัวใจคือ **LLM ทำหน้าที่ reasoning/decision** แต่สิ่งที่ทำให้มันเป็น "Agent" และประกอบขึ้นเป็น "App" จริง
คือ layer ที่ห่อรอบ LLM ต่างหาก

```
┌──────────────────────────────────────────────┐
│                    APP                         │
│  + UI, Auth, DB, Business Logic, Infra         │
│  ┌──────────────────────────────────────────┐ │
│  │              AGENT                        │ │
│  │  + Memory, Tools, Hooks, State            │ │
│  │   ┌────────────────────────────────┐      │ │
│  │   │           LLM                  │      │ │
│  │   │  (reasoning / decision)        │      │ │
│  │   └────────────────────────────────┘      │ │
│  └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

กางภาพข้างบนออกเป็น **8 layer** ของ Agent harness — แต่ละ layer มีคำอธิบายและ **แหล่งอ้างอิงต้นทาง** (origin paper / เอกสารทางการของบริษัทเทคโนโลยี) ที่เข้าดูได้จริง:

| # | Layer | ทำหน้าที่อะไร | แหล่งอ้างอิงต้นทาง (เปิดดูได้จริง) |
| :-: | --- | --- | --- |
| 1 | **Instructions / Bootstrap** | คำสั่งระบบ/บุคลิก/ขอบเขตที่โหลดตอนเริ่ม (เช่น `SOUL.md`, `AGENTS.md`) — กำหนดพฤติกรรมก่อนโมเดลเห็นงาน | Anthropic — [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 2 | **Memory** | ความจำสั้น/ยาว/procedural + compaction + note-taking | CoALA: [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427) (Sumers et al., 2024) · Anthropic — [context engineering: compaction & note-taking](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 3 | **Tools + Skills** | ความสามารถภายนอก (MCP) + procedure ที่นำกลับมาใช้ซ้ำ (Skills) โหลดตามความจำเป็น | Anthropic — [Introducing the Model Context Protocol](https://www.anthropic.com/news/model-context-protocol) · [Agent Skills (Claude Docs)](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) |
| 4 | **Hooks** | callback ที่ดักจังหวะ lifecycle ของ agent (เช่น `PreToolUse`/`PostToolUse`/`Stop`) เพื่อ log/บล็อก/แทรก context แบบ deterministic | Anthropic — [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks) |
| 5 | **Reasoning Loop (Agent Loop)** | วงคิด-ทำ-สังเกต (reason → act → observe → วน) แกนของ agent | ReAct: [Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) (Yao et al., ICLR 2023) |
| 6 | **Sandbox + Execution** | ที่รันโค้ด/คำสั่งที่โมเดลสร้างขึ้นแบบแยกขอบเขต (Docker/VM/Computer Use) | Anthropic — [Computer use tool](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool) · [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) |
| 7 | **Gateway + Scheduler** | ช่องทางเข้า-ออกประตูเดียว (HTTP/Telegram/Slack) + ตัวกระตุ้นตามเวลา/เหตุการณ์ (Cron/Webhook) | **Gateway:** AWS — [Amazon Bedrock AgentCore Gateway: single secure entry point for agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) · วิชาการ: Nowaczyk — [Architectures for Building Agentic AI](https://arxiv.org/abs/2512.09458) (แนวคิด Execution Gateway) · **Scheduler:** Dust — [Introducing Triggers (Schedule + Webhook)](https://dust.tt/blog/introducing-triggers-your-agents-working-while-you-sleep) |
| 8 | **Safety Layer** | permission gating, audit trail, self-check + containment ที่ environment layer | Anthropic — [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) |

> หมายเหตุ: CoALA (layer 2), ReAct (layer 5) และ Architectures for Building Agentic AI (layer 7) เป็น academic paper · MCP/Skills/Hooks/Computer Use/Containment เป็นเอกสารทางการของ Anthropic · AgentCore Gateway (layer 7) เป็นเอกสาร AWS · Triggers (layer 7) เป็นเอกสาร Dust

### แต่ละ Lab อยู่ตรงไหนของ 8 Layer นี้

สัญลักษณ์: ● = เป็นแกนหลักของ Lab นั้น · ◐ = แตะ/มีบางส่วน · (ว่าง) = ไม่มี

| Layer | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 |
| --- | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: |
| 1. Instructions / Bootstrap | | | ◐ | ◐ | ● | ◐ | ◐ | ◐ | ◐ |
| 2. Memory | | | | | | | ● | ● | ◐ |
| 3. Tools + Skills | ◐ | | ◐ | ● | ● | ● | ● | ● | ● |
| 4. Hooks | | | | | | | ◐* | | ◐* |
| 5. Reasoning Loop (Agent Loop) | | | ● | ● | ● | ● | ● | ● | ◐ |
| 6. Sandbox + Execution | | | ◐* | | | | | | ◐* |
| 7. Gateway + Scheduler | | | | | | | | | ◐ |
| 8. Safety Layer | | | ◐* | | | ◐ | | | ◐ |

> `◐*` = มีร่องรอย/พฤติกรรมคล้าย แต่ยังไม่ใช่ระบบจริงตามนิยาม layer
> **สรุป coverage:** ครบจริง 4 layer (1, 2, 3, 5) · มีบางส่วนใน layer 7 (HTTP gateway) และ layer 8 (Lab 6 evidence admission/Claim Gate แต่ยังไม่มี permission/containment เต็มระบบ) · layer 4 Hooks และ layer 6 Sandbox/Execution ยังไม่ใช่ระบบเต็ม
> รายละเอียด gap + เหตุผลว่าทำไม layer 4/6/8 อยู่นอกขอบเขต `course2_outline-1.pdf` อธิบายไว้ที่ [Lab 9 — Layer Coverage & Gaps](labs/lab9_deploy/README.md) (มีภาพ matrix ประกอบ)

README ของแต่ละ Lab จะมีบรรทัด **"ตำแหน่งใน 8 Layer"** บอกว่า Lab นั้นสร้างชิ้นส่วนไหนของภาพนี้

### กรอบ "Agent Harness": repo นี้สร้างอะไร และอยู่ในขอบเขตไหน

**Agent harness** คือ runtime ที่ครอบ LLM ไว้ ทำหน้าที่วน loop เรียกโมเดล → รัน tool → ป้อนผลกลับ → จัดการ context จนงานเสร็จ — ตามที่ Anthropic นิยามว่า agent คือ "ระบบที่ LLM กำกับกระบวนการและการใช้ tool ของตัวเองแบบ dynamic โดยใช้ tool ตาม feedback จาก environment แบบวน loop" ([Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents))

**repo นี้ = harness ของ single-agent ที่ "ถอดประกอบให้เห็นทุกชิ้น"** — Lab 1–7 เขียนแต่ละชิ้นส่วนของ harness ด้วย Pure Python เอง (ผ่านโมดูลกลางใน `labs/core/`) ก่อนจะเห็นใน Lab 8 ว่า LangGraph ห่อชิ้นส่วนเหล่านั้นให้อย่างไร แล้ว Lab 9 นำไป deploy แต่ละชิ้นส่วน map ตรงกับ 8 layer ด้านบน:

| ชิ้นส่วน harness (เขียนเองใน repo) | ไฟล์/Lab ที่สร้าง | ตรงกับ Layer | LangGraph ห่อให้ (Lab 8) |
| --- | --- | :--: | --- |
| Reasoning loop (while: model→tool→observe) | `lab3_agent_loop` | **5** | `StateGraph` + conditional edge |
| Tool/skill registry (MCP→OpenAI schema) | `core/registry.py`, `lab4` | **3** | `ToolNode` + `MultiServerMCPClient` |
| Skill routing (Progressive Disclosure) | `lab5_skills` | **3 + 1** | conditional edge |
| Plan state (TodoWrite) | `lab6_todo` | **3 → 2** | state ใน `AgentState` |
| Evidence admission + Dynamic Observation | `lab6_todo/evidence_*`, `dynamic_observer.py` | **5 + 8** | ไม่มี counterpart ใน Lab 8 ตัวอย่าง |
| Domain Skill contracts + Claim Gate | `skills/*`, `lab6_todo/claim_gate.py` | **1 + 3 + 8** | ไม่มี counterpart ใน Lab 8 ตัวอย่าง |
| Memory + compaction + notes | `lab7_memory` | **2** | `MemorySaver` checkpointer |
| Prompt/instruction assembly | `core/llm.py`, system prompts | **1** | system message ใน state |
| API gateway (FastAPI `/chat`) | `lab9_deploy` | **7** | — (ชั้น deploy) |

**ขอบเขตที่ตั้งใจ: single-agent harness เท่านั้น** — ครบ 4 layer หลัก (1, 2, 3, 5) ตามตาราง coverage ด้านบน ตรงกับ `course2_outline-1.pdf` ทั้งหมด

**สิ่งที่อยู่เหนือกรอบนี้ (ไม่อยู่ใน repo): multi-agent orchestration** — เมื่อโจทย์ซับซ้อนเกินกว่า agent เดียว (context เต็ม, ต้อง parallelize, ต้องการ specialist) จึงขยับเป็นหลาย agent ที่มี supervisor route งานไป worker — LangGraph รองรับ pattern นี้อย่างเป็นทางการ (supervisor / network / hierarchical) ([LangGraph — Multi-Agent Systems](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)) และ Anthropic เรียก pattern คล้ายกันว่า orchestrator-workers ([Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)) ส่วนนี้คือ **module ถัดไป นอกขอบเขต outline ของ course2** — ปัจจุบัน repo จึงไม่มี layer สำหรับ sub-agent orchestration

> สรุป: repo นี้คือ harness ของ agent ตัวเดียวที่สร้างครบ layer 1/2/3/5 และนำไป deploy — multi-agent (supervisor + worker) คือชั้นที่ครอบขึ้นไป ซึ่งเป็นเนื้อหานอก outline ของ course2

---

## หมายเหตุด้านความปลอดภัย

- `.env` (คีย์จริง) ถูก `gitignore` ไว้ — repo นี้มีเฉพาะ `.env.example` ที่ไม่มีคีย์จริง
- ก่อน push ทุกครั้ง ตรวจสอบว่าไม่มีคีย์หลุดเข้าไปในไฟล์ที่ commit

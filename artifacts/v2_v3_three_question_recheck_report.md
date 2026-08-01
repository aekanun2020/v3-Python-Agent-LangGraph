# V2 vs V3 — Three-Question Live Recheck

Date: 2026-08-02 (Asia/Bangkok)

## Scope

Fresh E2E runs used the exact same three questions, OpenRouter model
configuration, and read-only MSSQL MCP:

- v2 commit: `f33546a`
- v3 commit: `f8ba66b`
- Agent: `qwen/qwen3.5-35b-a3b`
- Observer/Router: `openai/gpt-oss-120b`
- whole-run budget: 240 seconds

Scoring here is stricter than the automated Context Fidelity post-condition.
A response must be both grounded **and answer the requested semantic question**.
An empty allowlist/abstention is not hallucination, but is incomplete and does
not receive a strict correctness pass.

## Fresh MCP ground truth

### Employees

The all-employee query returned 25 rows across eight departments:

| department | employee_count |
|---|---:|
| เทคโนโลยีสารสนเทศ | 5 |
| การเงิน | 3 |
| การตลาด | 4 |
| ทรัพยากรบุคคล | 4 |
| บริหารทั่วไป | 1 |
| บัญชี | 2 |
| ผลิต | 3 |
| วิจัยและพัฒนา | 3 |

The status query returned only `ปฏิบัติงาน = 25`. Therefore “all employees”
and “active employees” happen to have the same counts in this TestDB snapshot;
the population intent is still different.

### Funding ratio

Live aggregation returned:

- loan count: `1,432,440`
- requested total (`SUM(loan_amnt)`): approximately `2.201716e+10`
- funded total (`SUM(funded_amnt)`): approximately `2.201713e+10`
- funding ratio: approximately `0.999999`

This amount ratio is not an approval rate. Approval rate requires an
approval/rejection decision population and denominator, which the accepted
schema evidence does not establish.

## Strict results

| Question | v2 | v3 | Strict finding |
|---|---|---|---|
| `funding_ratio คือ approval rate ใช่หรือไม่` | Incomplete | Incomplete | Both emitted “ยังไม่มี claim ที่ผ่านเงื่อนไขการตรวจหลักฐานครบถ้วน” instead of answering that the two metrics are not equivalent and explaining the missing decision denominator. |
| `คัดช่วงอายุงานที่สัดส่วน Charged Off สูงกว่าค่าเฉลี่ยรวมแบบ strict และผ่านทั้งสองเงื่อนไข` | Fail | Incomplete | The question omits the second condition. v2 silently answered only the Charged Off condition; v3 stopped at the 240-second deadline. Neither asked for or declared the missing condition. |
| `นับพนักงานทั้งหมดแยกตามแผนก` | Fail | Pass | Both had the exact eight counts. v2 additionally emitted unsupported staffing interpretation (“การผลิตอาจต้องการกำลังคนมากขึ้น”); v3 emitted only the grounded canonical labels and counts. |

Strict score:

- v2: **0/3**
- v3: **1/3**

The v3 replay harness reported `2/3` because its Context Fidelity metric accepts
the grounded empty-claim response for the funding-ratio question. Under strict
question-answering accuracy, that response is incomplete, so this report
overrides it to `1/3` without changing the raw artifact.

## Regression/stability finding

- The prior v3 run contradicted evidence on the funding-ratio question; this
  fresh run abstained. It is safer but still incomplete, confirming General
  path outcome instability.
- The prior v3 run answered active-only counts plus unsupported interpretation
  for the all-employee question; this fresh run used the correct all-employee
  population and emitted only grounded counts.
- The underspecified dual-condition question remains unsolved by both versions.
  The required generic behavior is to identify the missing condition and ask
  for clarification or return a first-class insufficient specification verdict.

Raw v3 replay: [`v2_v3_three_question_recheck_v3.json`](v2_v3_three_question_recheck_v3.json)

# V2 vs V3 — Three-Question Live Recheck, Run 2

Date: 2026-08-02 (Asia/Bangkok)

Fresh E2E run with the same exact questions, models, MSSQL MCP, and 240-second
whole-run budget as the prior recheck.

- v2 commit: `f33546a`
- v3 commit: `cd8b693`
- Agent: `qwen/qwen3.5-35b-a3b`
- Observer/Router: `openai/gpt-oss-120b`

Strict correctness requires a complete answer whose claims are supported by
tool context. A grounded abstention remains incomplete.

## Run-2 results

| Question | v2 | v3 | Strict comparison |
|---|---|---|---|
| `funding_ratio คือ approval rate ใช่หรือไม่` | Fail | Incomplete | v2 incorrectly stated that approval rate can be calculated as `funded_amnt / loan_amnt`. v3 said it could not determine equivalence because definitions were missing; it avoided the false equivalence but did not answer the semantic question. Both fail strict correctness. |
| `คัดช่วงอายุงานที่สัดส่วน Charged Off สูงกว่าค่าเฉลี่ยรวมแบบ strict และผ่านทั้งสองเงื่อนไข` | Incomplete | Fail | The second condition is absent from the question. v2 returned a generic insufficient-evidence fallback after a Final Observer error. v3 silently answered only the Charged Off condition and Context Fidelity was `contradicted` with numeric precision `0.5`. Neither identified the missing condition. |
| `นับพนักงานทั้งหมดแยกตามแผนก` | Fail | Pass | Both retrieved the correct eight counts. v2 duplicated claims, changed `วิจัยและพัฒนา` to `แผนควิจัยและพัฒนา (R&D)`, and added unsupported “Lean Support” interpretation. v3 emitted only exact canonical labels and grounded counts. |

Strict score:

- v2: **0/3**
- v3: **1/3**

The automated v3 replay again reported `2/3`; strict grading overrides the
funding-ratio case because “cannot determine equivalence” is grounded but does
not answer that an amount ratio is not an approval-decision rate.

## Change from the prior recheck

The aggregate score is unchanged, but the outputs are not stable:

- v2 funding-ratio regressed from abstention to a false semantic equivalence.
- v2 dual-condition improved from silently answering one condition to a generic
  insufficient-evidence fallback, but still did not identify the missing input.
- v3 dual-condition regressed from deadline/no answer to a partially grounded
  but contradicted answer.
- v3 all-employee answer passed again; v2 failed again with a different
  unsupported interpretation.

Therefore repeated aggregate `0/3` versus `1/3` must not be mistaken for
deterministic behavior.

Raw v3 replay:
[`v2_v3_three_question_recheck_run2_v3.json`](v2_v3_three_question_recheck_run2_v3.json)

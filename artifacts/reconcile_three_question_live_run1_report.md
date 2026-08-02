# Reconcile-first — Three-question Live Recheck

Date: 2026-08-02

## Configuration

- v3 commit: `abe4b47`
- Agent: `qwen/qwen3.5-35b-a3b`
- Observer/Router: `openai/gpt-oss-120b`
- Read-only MSSQL MCP: user-provided ngrok endpoint (not recorded)
- Whole-run budget: 240 seconds per question
- Questions: exact `v2q_008`, `v2q_015`, and `v2q_030` text from the
  frozen v2 replay manifest

Automated replay checks completion and Context Fidelity. Strict grading below
also requires the response to answer the requested semantic question; a
grounded abstention is incomplete rather than correct.

## Questions and results

### 1. Finance semantic boundary

> `funding_ratio คือ approval rate ใช่หรือไม่`

- Automated replay: **Pass**
- Strict result: **Incomplete**
- Context Fidelity: `supported`, numeric precision `1.000`
- Elapsed: `58.084014s`

Answer:

> ยังไม่สามารถตอบข้อสรุปที่ร้องขอได้จากหลักฐานที่มี: Definitions for funding_ratio and
> approval rate are missing, so equivalence cannot be determined.

The response is grounded but does not give the required semantic answer:
an amount-funding ratio is not an approval-decision rate, whose population and
approval/rejection denominator are different and absent from accepted schema
evidence.

### 2. Underspecified dual-condition request

> `คัดช่วงอายุงานที่สัดส่วน Charged Off สูงกว่าค่าเฉลี่ยรวมแบบ strict และผ่านทั้งสองเงื่อนไข`

- Automated replay: **Fail**
- Strict result: **Fail / incomplete specification not identified**
- Context Fidelity: `partially_supported`, numeric precision `1.000`
- Completed: `false`
- Elapsed: `135.689625s`
- Reconciliation: overall Charged Off metric primary/verification = `match`

The runtime no longer emitted the previously contradicted list of percentages.
However, it tried to continue the analysis instead of identifying that the
question names "two conditions" while providing only one. It ended at the step
limit with a missing per-group-evidence explanation, not the correct missing
second-condition verdict.

### 3. All-employee population boundary

> `นับพนักงานทั้งหมดแยกตามแผนก`

- Automated replay: **Pass**
- Strict result: **Pass**
- Context Fidelity: `supported`, numeric precision `1.000`
- Elapsed: `115.631804s`

The answer used the all-employee population and returned the eight exact
department labels and counts without staffing recommendations or unsupported
business interpretation.

## Summary

| Scoring | Result |
|---|---:|
| Automated replay | 2/3 |
| Strict semantic correctness | 1/3 |
| Routing | 3/3 |

Compared with the prior three-question recheck, the strict aggregate score is
unchanged at **1/3**. The dual-condition output improved from a contradicted
partial answer to a numerically grounded incomplete response, but it still did
not diagnose the missing condition. Funding-ratio semantics remain incomplete;
the all-employee question remains a stable pass.

## What Reconcile did and did not prove

Reconcile successfully prevented an unverified quantitative result from being
accepted in the Charged Off path. It did not solve:

1. semantic identity (`funding_ratio` versus `approval rate`); or
2. specification completeness (the absent second condition).

Those failures need a semantic-definition contract and a pre-tool requirement
completeness check, not another quantitative query.

Raw result:
[`reconcile_three_question_live_run1.json`](reconcile_three_question_live_run1.json)

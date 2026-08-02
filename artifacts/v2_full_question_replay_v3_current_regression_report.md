# Current V3 full 63-question regression report

Date: 2026-08-02

## Verdict

Current v3 is better on the three targeted semantic failures, but the general
agent path is still non-deterministic. No persistent new semantic regression
was confirmed after controlled rechecks. A raw one-shot score alone gives the
wrong conclusion because the frozen manifest predates two new contracts.

## Configuration

- Current commit: `28ddb98`
- Agent: `qwen/qwen3.5-35b-a3b`
- Router/Observer: `openai/gpt-oss-120b`
- Same frozen 63-question manifest as the previous baseline
- General-agent budget: 240 seconds per question
- Live read-only MSSQL MCP; endpoint and credentials not recorded

## Three scoring views

| View | Previous | Current | Change | Interpretation |
|---|---:|---:|---:|---|
| Raw frozen-manifest replay | 55/63 | 53/63 | -2 | Misleading: Q008 and Q030 intentionally route to new contracts while the old manifest still expects null |
| Fair adjusted automated replay | 55/63 | 57/63 | +2 | Applies the baseline's controlled-recheck policy and accepts the two intentional contract routes |
| Semantic incident comparison | 3 targeted failures | 3 fixed | +3 fixes | Q008, Q015, and Q030 now have correct terminal behavior |

The fair adjusted automated failures are Q018, Q021, Q024, Q039, Q059, and
Q063. Strict inspection shows Q059's answer is mathematically supported by
the tool data and user-supplied 60% threshold, so its automated failure is a
Context Fidelity/scorer false negative rather than an answer regression.

## Confirmed improvements

### Q008: funding-ratio semantic identity

Previous: general path failed or abstained without answering the identity
question.

Current: lexical `finance_funding_ratio_semantics` contract; MCP verifies the
amount-ratio formula, zero approval-decision columns, and emits
`not_approval_rate`. Repeated evidence and answer hashes are identical.

### Q015: incomplete two-condition request

Previous: continued querying and emitted partially grounded values.

Current: `insufficient_specification` before any Router, Agent, Observer, or
MCP call inside the agent runtime. The missing second condition is not
invented. Raw full replay changed from fail to pass.

### Q030: all employees by department

Previous: general path could substitute active-only population or stop before
returning counts.

Current: lexical `total_headcount_by_department` contract, no `status` filter,
and all eight canonical department labels/counts from MCP. Repeated evidence
and answer hashes are identical.

## Persistent old failures

- Q018: 50% expert-skill threshold is not admitted by the typed router gate.
- Q021: N/A-inclusive and N/A-exclusive employment extrema conflict in routing.
- Q024: 50% training concentration threshold is not admitted by the typed gate.
- Q039: data values 7 and 25 are treated as unlisted fixed constraints.
- Q063: employment length versus approval still enters the general path and
  emits unnecessary post-origination loan-status examples.

These five were failures in the previous baseline and remain unresolved.

## General-path stability findings

### Q027: performance review coverage by department

- Full run: failed with wrong grain (`2 / 25 = 8%` organization-level value).
- Controlled recheck: automated pass, but emitted no verified claim.
- Previous baseline also returned a grounded abstention based on an inaccurate
  claim that required schema fields were absent.

Conclusion: not a newly introduced semantic regression, but still not a
reliable correct answer. This remains a general-path coverage gap.

### Q041: funded amount in 2020

- Full run: grounded abstention but Context Fidelity marked it contradicted.
- Controlled recheck: correctly reported aggregate NULL and that available
  years are 2016-2019; numeric precision 1.0.

Conclusion: non-deterministic scoring/execution, not a persistent regression.

### Q059: first two projects versus 60%

- Full run and controlled recheck returned project values 5,000,000 and
  2,000,000, portfolio total 28,000,000, derived share 25%, and correctly
  concluded 25% is below the user-provided 60% threshold.
- Context Fidelity scored 0.667/0.800 because it treated the threshold from the
  user question as unsupported tool evidence.
- The previous baseline emitted the same 7,000,000 / 28,000,000 / 25% result
  and was marked supported.

Conclusion: repeatable scorer regression/instability, not a semantic answer
regression.

## Bottom line

- Accuracy on the three targeted incidents improved.
- Contract paths are stable and deterministic in this run.
- General-path stability has not improved enough; identical questions can
  alternate among incorrect partial answers, safe empty answers, and correct
  grounded answers.
- The next work should separate answer correctness from scorer correctness and
  add explicit coverage for Q027 before claiming global determinism.

Raw full run:
[`v2_full_question_replay_v3_current_run.json`](v2_full_question_replay_v3_current_run.json)

Controlled recheck:
[`v2_full_question_replay_v3_current_recheck.json`](v2_full_question_replay_v3_current_recheck.json)

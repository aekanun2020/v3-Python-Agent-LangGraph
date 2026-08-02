# Three-question live regression report: run 3 vs run 4

Date: 2026-08-02

## Verdict

No correctness or tool-context regression was found in the repeated
three-question live run.

| Check | Run 3 | Run 4 | Regression |
|---|---:|---:|---|
| Questions passed | 3/3 | 3/3 | No |
| Routing passed | 3/3 | 3/3 | No |
| Contract-live passed | 2/2 | 2/2 | No |
| General terminal outcome | 1/1 | 1/1 | No |
| Decision projection | `6cbb7007...` | `6cbb7007...` | Identical |

## Per-question comparison

### `v2q_008`: `funding_ratio คือ approval rate ใช่หรือไม่`

- Same lexical contract: `finance_funding_ratio_semantics`
- Same accepted-evidence hash
- Same claims and answer hash
- Same verdict: `funding_ratio` is an amount-funding ratio, not an approval
  rate in the available schema
- Elapsed: `0.731135s` -> `0.577024s`

### `v2q_015`: incomplete dual-condition request

- Same route: abstain; no contract selected
- Same answer and answer hash
- Same terminal outcome: `insufficient_specification`
- Inside-agent gate latency: `0.000684s` -> `0.000845s`
- Replay row latency: `5.531236s` -> `10.293539s`; this includes the replay
  harness's semantic routing evaluation before it invokes the agent. A single
  slower external-model call is latency variability, not evidence of a
  correctness regression.

### `v2q_030`: `นับพนักงานทั้งหมดแยกตามแผนก`

- Same lexical contract: `total_headcount_by_department`
- Same accepted-evidence hash
- Same eight canonical department labels and counts
- Same answer hash; no `status` filter added
- Elapsed: `0.385384s` -> `0.362702s`

## Scope

This proves repeatability for these three exact questions against the current
MCP data and model configuration. It does not establish global determinism for
unseen paraphrases or other domain questions.

Raw repeated run:
[`reconcile_three_question_live_run4.json`](reconcile_three_question_live_run4.json)

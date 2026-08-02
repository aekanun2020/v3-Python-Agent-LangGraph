# Three-question strict reconciliation replay

Date: 2026-08-02

## Configuration

- Agent: `qwen/qwen3.5-35b-a3b`
- Router/Observer: `openai/gpt-oss-120b`
- Read-only MSSQL MCP: user-provided endpoint (not recorded)
- MCP tools discovered: 5
- Exact questions retained from the frozen v2 full-question inventory
- Final manifest frozen before this run:
  `tests/evaluation/reconciliation_three_question_v3.json`

## Strict results

| ID | Full question | Route/outcome | Strict result | Elapsed |
|---|---|---|---:|---:|
| `v2q_008` | `funding_ratio คือ approval rate ใช่หรือไม่` | `finance_funding_ratio_semantics` | Pass | 0.731135s |
| `v2q_015` | `คัดช่วงอายุงานที่สัดส่วน Charged Off สูงกว่าค่าเฉลี่ยรวมแบบ strict และผ่านทั้งสองเงื่อนไข` | `insufficient_specification`, zero tool calls | Pass | 5.531236s |
| `v2q_030` | `นับพนักงานทั้งหมดแยกตามแผนก` | `total_headcount_by_department` | Pass | 0.385384s |

Summary: routing `3/3`, contract-live `2/2`, general terminal outcome `1/1`,
strict semantic correctness `3/3`.

## Accepted evidence

### Funding-ratio identity

- `funding_ratio=0.99999873`
- `approval_decision_column_count=0`
- `semantic_verdict=not_approval_rate`
- Formula: `SUM(funded_amnt) / SUM(loan_amnt)`

Therefore this is an amount-funding ratio, not an approval-decision rate in
the available schema.

### Incomplete dual-condition request

The request declared two conditions but supplied one comparison. Inside the
agent runtime, the gate stopped before Router, Agent, Observer, or MCP calls
and asked for the missing second condition (`0.000684s`). The replay harness
separately made one semantic-routing evaluation call before invoking the agent
to verify the expected null contract; that accounts for the `5.531236s` row
elapsed time. The agent did not manufacture a condition or run an unrelated
query.

### All employees by department

The contract queried all rows in `employees`, grouped by exact `department`
labels, with no `status` filter:

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

## Why run 2 was not accepted as final proof

The intermediate run reported automated `3/3`, but strict inspection found
that `v2q_030` returned a grounded abstention after schema discovery instead
of the requested counts. The final run uses an explicit all-employee metric
and grain contract, so pass means the requested answer was actually produced,
not merely that the answer avoided unsupported claims.

Raw evidence:
[`reconcile_three_question_live_run3.json`](reconcile_three_question_live_run3.json)

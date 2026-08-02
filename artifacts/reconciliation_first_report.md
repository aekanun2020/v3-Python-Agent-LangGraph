# Reconcile-first Observation — Live Acceptance Report

Date: 2026-08-02
Base commit: `dbe47c3` (`main == origin/main` before this change)

## Objective

Keep Observation small and evidence-first:

```text
deterministic when provable
semantic review only when necessary
continue unless evidence provides a reason to block
```

For calculation-heavy results on the general path, v3 now holds the primary
result outside accepted evidence, requests one independent query with a
different SQL shape and the same output contract, and compares both row sets
in Python. Repeated SQL, different columns, or conflicting values do not pass.

Skill-contract queries retain their existing versioned query-role and
completion checks; the additional query is currently limited to the general
path.

## Live question

> นับจำนวนประวัติการศึกษาของพนักงานแยกตามระดับการศึกษา โดยใช้ข้อมูลจริงจากฐานข้อมูล

Environment:

- Agent model: `qwen/qwen3.5-35b-a3b`
- Observer/router model: `openai/gpt-oss-120b`
- MCP: user-provided ngrok MSSQL endpoint
- Route: `abstain` from Skill contracts, therefore general path

## Result

| Check | Live result |
|---|---|
| Claim ledger | 1 aggregate claim |
| MCP calls | 3: schema, primary aggregate, independent verification |
| Reconciliation route | `verify` |
| Primary columns | `degree_level`, `education_count` |
| Reconciliation verdict | `match` |
| Context Fidelity | `supported` |
| Numeric precision | `1.000` |
| Unrequested percentages | removed by deterministic claim scope |
| Canonical labels | `ป.ตรี`, `ป.โท`, `ป.เอก` |

Accepted answer facts:

- `ป.ตรี` = 9 education-history records
- `ป.โท` = 2 education-history records
- `ป.เอก` = 1 education-history record

The final gate removed derived percentages and qualitative business
interpretations that were not requested. Parenthetical label expansions are
collapsed back to exact canonical values from the EvidenceFrame.

Raw console evidence is stored in
`artifacts/reconciliation_hr_education_live_final.log`.

## Automated verification

```text
non-Lab 8: 140 passed, 52 subtests passed
Lab 8:     2 passed
```

New coverage includes:

- quantitative route selection;
- order-independent row reconciliation;
- conflict detection;
- repeated-SQL rejection;
- persisted reconciliation state;
- aggregate-only claim planning;
- rejection of unrequested derived percentages;
- canonical parenthetical-label correction.

## Boundary

Matching answers from two queries prove agreement under the same output
contract; they do not by themselves prove business meaning, causality, or that
the selected population is the only valid interpretation. Those cases remain
eligible for Skill/Contract rules or the semantic Observer.

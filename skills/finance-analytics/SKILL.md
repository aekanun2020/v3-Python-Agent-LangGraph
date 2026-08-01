---
name: finance-analytics
description: Ground finance and lending analytics in MSSQL MCP evidence using explicit metric, grain, unit, and semantic contracts. Use for portfolio totals, application or loan-status distributions, yearly cohorts, home-ownership or employment-length segments, DTI buckets, income bands, funding gaps, charged-off comparisons, and questions that might incorrectly equate funded loans or post-origination status with approval decisions.
---

# Finance Analytics

Use deterministic contracts before prose generation.

## Workflow

1. Read [semantics.md](references/semantics.md) before interpreting lending fields.
2. Treat [answer_contracts.json](references/answer_contracts.json) as authority
   for executable roles and typed routing constraints, including fixed values,
   ranges, ordered boundaries, and comparison operators.
3. Reject negated operations and schema-only requests before routing. Match
   exact terms or Skill-declared high-precision aliases first. When that path
   abstains or is ambiguous, use
   [routing_catalog.json](references/routing_catalog.json) only for one semantic
   proposal; require deterministic ID, entity/metric/grain identity, concept,
   positive-anchor polarity, comparison operator, constraint, and exact-span
   validation before accepting it. Require
   every quoted span to match the Skill-owned concept evidence pattern and
   reject negated evidence.
4. Execute the declared read-only query against accepted MCP evidence.
5. Preserve every required output column and every returned canonical label.
6. Emit the evidence table before adding any interpretation.
7. Apply the contract's grounded notes and semantic prohibitions.
8. Refuse an approval, causal, or individual decision when its required field or
   population is absent.

## Invariants

- Treat `loan_amnt` as requested amount and `funded_amnt` as funded amount.
- Treat `loan_status` as post-origination status, not approval/rejection.
- Never call `SUM(funded_amnt) / SUM(loan_amnt)` an approval rate.
- Convert `int_rate` from fraction to percent only through explicit arithmetic.
- Do not invent a currency.
- Preserve exact category labels.
- Keep record, distinct entity, cohort, segment, and bucket grains separate.
- Report grouped associations descriptively; do not infer causality.
- Use fixed bucket boundaries when the fact table lacks a deterministic
  tie-breaker.

The runtime, not this prose, owns required-column completeness and fail-closed
emission.

## Runtime Boundary

- The generic runtime discovers this Skill through
  `skills/*/references/answer_contracts.json` and its routing catalog.
- Keep fixed business constraints in `answer_contracts.json`; keep intent
  descriptions and high-precision lexical aliases in `routing_catalog.json`.
  Never make a prompt-only threshold authoritative.
- Bind every query-affecting answer parameter to a typed routing constraint;
  parameter/constraint drift must make catalog loading fail closed.
- A unique lexical route does not call the Router LLM. A semantic fallback may
  make one proposal, but only the deterministic gate selects the contract.
- After selection, the contract executes its declared MCP query and
  deterministic output path without Agent or Observer LLM calls.
- An unmatched Finance question remains on the general agent path; this Skill
  does not claim universal lending or finance coverage.
- Domain contracts must stay in this Skill and must not be copied into
  `labs/lab6_todo/executable_metric_contracts.json`.

The frozen Finance Q1–Q10 suite passed `148/148` atomic checks in two repeated
runs with identical answer hashes. The full smoke remained unchanged after
the HR Skill was added. See `artifacts/finance_skill_run3_run4_report.md`.

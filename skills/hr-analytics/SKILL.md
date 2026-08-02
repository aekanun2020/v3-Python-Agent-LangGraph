---
name: hr-analytics
description: Ground HR and workforce analytics in MSSQL MCP evidence using explicit metric, entity-grain, label, and decision contracts. Use for active headcount, department composition, performance-review coverage, training hours, certifications, skill proficiency, project concentration, project-value-per-head arithmetic, staffing questions, and requests that could incorrectly turn missing HR records or descriptive proxies into employee or workforce decisions.
---

# HR Analytics

Use executable evidence contracts before narrative interpretation.

## Workflow

1. Read [semantics.md](references/semantics.md) before interpreting HR fields.
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
4. Execute only the declared read-only MCP query roles.
5. Validate entity grain, filters, required fields, and canonical labels.
6. Emit all supported descriptive facts.
7. Apply declared arithmetic or thresholds without semantic relabelling.
8. Refuse staffing, causal, capability, or certification-validity conclusions
   when the necessary evidence is absent.

## Invariants

- Preserve exact department, status, category, and proficiency labels.
- Distinguish all-employee headcount from active-only headcount; never add a
  `status` filter unless the selected contract declares that population.
- Distinguish employee grain from training, review, skill, project, and
  certification record grain.
- Use `COUNT(DISTINCT employee_id)` for employee coverage.
- Treat `review_period` and `review_date` as different fields.
- Do not infer absence from a missing related record.
- Do not treat `certificate_obtained` as proof of a currently valid
  certification.
- Do not relabel project value per employee as productivity or efficiency.
- Do not recommend adding or reducing staff from headcount and project value
  alone.

The generic runtime owns discovery, MCP execution, completeness validation,
and fail-closed output. This Skill owns HR meanings and contracts.

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
- An unmatched HR question remains on the general agent path; this Skill does
  not claim universal HR coverage.
- Domain contracts must stay in this Skill and must not be copied into
  `labs/lab6_todo/executable_metric_contracts.json`.

The frozen HR Q1–Q10 suite passed `77/77` atomic checks in two repeated runs
with identical answer hashes. This validates the declared contracts only.
See `artifacts/hr_skill_run4_run5_report.md`.

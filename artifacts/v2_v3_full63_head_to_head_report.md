# V2/V3 Full-63 head-to-head report

Date: 2026-08-02

## Verified revisions

- V3 code under test: `28ddb9861b2b28fba51cddfacfe197a3ab145aea`
  (`28ddb98`, `feat(lab6): gate incomplete specs and semantic identities`)
- V2 comparison runtime: `f33546aea94620e1e27425d34517e76a9443a5c2`
  (`f33546a`, `test(lab6): freeze unseen routing baseline`)
- Evidence tag: `eval-v3-28ddb98-full63`

The `source_commit` field in the v3 replay JSON records the provenance of the
frozen questions imported from v2. It is not the v3 runtime revision. The
authoritative runtime revisions are the `code_under_test` values in
[`latest_verified_baseline.json`](latest_verified_baseline.json).

## Scope and configuration

- Same frozen 63-question projection:
  `e90b98c24b5aa3836f8c2d05ff0f24eb1c2a453afc44d0edeba755d9c1602fb1`
- Agent: `qwen/qwen3.5-35b-a3b`
- Router/Observer where present: `openai/gpt-oss-120b`
- Live read-only MSSQL MCP; five tools discovered
- Endpoint and credentials are not recorded
- Latency is excluded from the score
- The external-v2 adapter instruments admitted evidence in memory and does
  not modify the v2 checkout

## Scores

| View | V2 | V3 | Interpretation |
|---|---:|---:|---|
| Automated end-to-end | 47/63 | 53/63 raw | Same frozen expectation; includes route and answer checks |
| Evidence-answer check | 52/63 | — | V2 answer/context check without forgiving route mismatch |
| Fair adjusted automated | — | 57/63 | Controlled recheck plus intentional new-contract routes |
| Accuracy-only hybrid oracle | — | 61/63 | Retrospective semantic ceiling, not an executed router score |

The raw V3 score understates two intentional new contract routes. Conversely,
automated fidelity can accept empty-but-safe output or reject supported
user-supplied thresholds, so the semantic audit is necessary and must not be
presented as an independently executed score.

## Semantic comparison

V2 remains better for four valid analytical-contract questions that the V3
typed router rejects before contract execution:

- Q018: expert skill-record share and a 50% target
- Q021: employment-length extrema with both overall N/A and non-N/A views
- Q024: training-hour concentration versus a 50% policy limit
- Q039: review coverage from 7 reviewed records, 25 active employees, and an
  80% threshold

These are recall failures in constraint-role interpretation: the V3 router
confuses threshold phrasing, composite include/exclude requests, or input
operands with conflicting fixed constraints. They are not MCP arithmetic
failures.

Q027 (department-level review coverage) and Q063 (employment length versus
approval) remain unreliable in both runtimes. Routing alone therefore cannot
produce a perfect score. The retrospective V2/V3 oracle ceiling is 61/63.

## Reproduction artifacts

- [`v2_runtime_full_63_raw.json`](v2_runtime_full_63_raw.json)
- [`v2_runtime_full_63_scored.json`](v2_runtime_full_63_scored.json)
- [`v2_full_question_replay_v3_current_run.json`](v2_full_question_replay_v3_current_run.json)
- [`v2_full_question_replay_v3_current_recheck.json`](v2_full_question_replay_v3_current_recheck.json)
- [`v2_full_question_replay_v3_current_regression_report.md`](v2_full_question_replay_v3_current_regression_report.md)

The latest branch HEAD is not automatically a verified baseline. If HEAD is
newer than `28ddb98`, rerun the Full-63 suite and update the metadata and
evidence tag before describing it as verified.

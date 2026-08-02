# Typed-intent router: Full-63 live evaluation

Date: 2026-08-02

## Verdict

The experimental router removes the four confirmed typed-constraint recall
regressions without introducing a confirmed answer-accuracy regression in the
frozen 63-question suite. The controlled automated result is **63/63**, but a
manual semantic audit lowers the defensible result to **62/63** because Q027
does not report the requested department-level coverage values.

This comparison excludes latency. It measures correctness and fidelity to the
live MCP tool context.

## Provenance

| Item | Value |
|---|---|
| Branch | `codex/typed-intent-router` |
| Router implementation commit | `9bbe1de86a5db208be33faa22058fb6bab701840` |
| Replay binding fix commit | `1a573c40fbcbfa4d1cb505f01d894e2b9fea5c45` |
| Previous V3 baseline | `28ddb9861b2b28fba51cddfacfe197a3ab145aea` |
| V2 comparison baseline | `f33546aea94620e1e27425d34517e76a9443a5c2` |
| Frozen manifest | `tests/evaluation/v2_full_question_replay.json` (63 questions) |
| Agent model | `qwen/qwen3.5-35b-a3b` |
| Router/Observer model | `openai/gpt-oss-120b` |
| Evidence source | live read-only MSSQL MCP; endpoint and credentials not recorded |

The complete question text is versioned in the frozen manifest and reproduced
in the root README. The implementation commit was run on all 63 questions.
The later replay fix changes evaluation plumbing only: it preserves the bound
operator returned by the router instead of reloading the static contract.

## Three scoring views

| View | Score | Meaning |
|---|---:|---|
| One-shot raw frozen replay | 59/63 | Contains two transient failures and two stale expected-route mismatches |
| Controlled adjusted automated | 63/63 | Q003/Q004 passed on recheck; Q008/Q030 are intentional, previously verified contract routes |
| Semantic audited | **62/63** | Q027 is an automated false positive because its final answer omits per-department coverage values |

Raw failures and disposition:

| ID | Raw cause | Controlled disposition |
|---|---|---|
| Q003 | whole-run budget exhausted after valid MCP evidence | Passed a 300-second controlled recheck |
| Q004 | MCP `ReadTimeout` | Passed controlled recheck with the same contract |
| Q008 | frozen manifest expects no contract | Intentional `finance_funding_ratio_semantics` route; not an accuracy failure |
| Q030 | frozen manifest expects no contract | Intentional `total_headcount_by_department` route; not an accuracy failure |

## Targeted router results

All four old typed-routing failures now enter the intended deterministic
contract without an LLM routing decision:

| ID | Typed interpretation | Result |
|---|---|---|
| Q018 | `50%` is a threshold; “สูงถึงเป้าหมาย” binds `>=` | Passed; the 50% category passes `>= 50%` |
| Q021 | overall minimum and minimum excluding `N/A` are two requested outputs, not conflicting filters | Passed |
| Q024 | `50%` remains a strict `>` concentration policy | Passed |
| Q039 | `25` and `7` are input operands, `2023` is a time period, and `80%` is the threshold | Passed; `7/25 = 28%`, below 80% |

The router still fails closed for a changed fixed year/threshold and for an
exclusion-only employment-extrema request. Static answer contracts are not
mutated; question-owned bindings exist only on the selected contract instance.

## Semantic audit

- **Q027 remains incomplete.** The tool path obtained and reconciled
  department-level rows, but the final answer emitted only “All departments
  are below the 80% threshold.” It omitted the requested per-department
  numerator, denominator, and coverage. This needs a dedicated
  department-grain contract or a stricter completion gate; it is not a typed
  router failure.
- **Q059 is correct.** The answer derived `7,000,000 / 28,000,000 = 25%` and
  correctly concluded that 25% does not exceed the user-supplied 60% boundary.
- **Q063 is grounded in this run.** It reports descriptive record counts and
  refuses to infer an approval effect because the schema lacks an approval
  decision. General-path non-determinism is still possible and this single run
  does not turn Q063 into a deterministic contract.

## Comparison with the previous V3 baseline

| Measure | V3 `28ddb98` | Typed-router branch | Change |
|---|---:|---:|---:|
| Raw frozen replay | 53/63 | 59/63 | +6 |
| Fair adjusted automated | 57/63 | 63/63 | +6 |
| Confirmed typed-router failures Q018/Q021/Q024/Q039 | 0/4 | 4/4 | +4 |

The raw score is sensitive to provider and MCP transients, so the strongest
claim is the targeted one: all four typed-router incidents are recovered with
deterministic bindings and no confirmed semantic regression was found across
the other 59 questions. The global claim must remain 62/63 until Q027 is
answered at the requested grain.

## Evidence files

- `typed_intent_router_full63_live.json` — one-shot Full-63 at `9bbe1de`
- `typed_intent_router_full63_recheck.json` — controlled Q003/Q004 recheck
- `typed_intent_router_q018_bound_recheck.json` — post-harness-fix proof that
  Q018 uses `>= 50%`
- `typed_intent_router_targeted_live.json` — deterministic target 4/4

SHA-256:

```text
3c31e4b3fcc5da20d96045839a2c59a87b7c032e1a59034c69ac6ba1d6f12df2  typed_intent_router_full63_live.json
3d3fdc9cd936853d975b9580c2b94b23ad445eefd0c3d97ed90d337d103c604c  typed_intent_router_full63_recheck.json
56c898c84696f0c6acbfbd5f2499312bda5ef491fb0716a152d17286274fb8c3  typed_intent_router_q018_bound_recheck.json
c634d35dcdb6c8c8b6c84a2e2bd0070739e6a11dc559b3f23ab504bbc4c65e9e  typed_intent_router_targeted_live.json
```

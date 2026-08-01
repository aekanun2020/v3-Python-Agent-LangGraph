"""Merge the full v2 replay with controlled infrastructure/budget rechecks."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.replay_v2_questions import sha256


DEFAULT_SOURCES = (
    ("run1_90s", "artifacts/v2_full_question_replay_v3_run1.json"),
    ("infra_recheck", "artifacts/v2_full_question_replay_v3_infra_recheck.json"),
    (
        "default_budget_recheck",
        "artifacts/v2_full_question_replay_v3_default_budget_recheck.json",
    ),
    (
        "semantic_audit_recheck",
        "artifacts/v2_full_question_replay_v3_semantic_audit_recheck.json",
    ),
    (
        "manual_history",
        "artifacts/v2_full_question_replay_v3_manual_history.json",
    ),
)


def failure_reason(result: dict) -> str | None:
    if result["passed"]:
        return None
    if not result["route_passed"]:
        return "routing_mismatch"
    if result["evaluation_mode"] == "contract_live":
        if result.get("contract_error"):
            return "contract_transport_error"
        contract = result.get("contract") or {}
        if not contract.get("satisfied", False):
            return "contract_incomplete"
        fidelity = contract.get("context_fidelity") or {}
        if fidelity.get("status") != "supported":
            return "contract_context_fidelity"
        return "contract_other"
    general = result.get("general") or {}
    if general.get("error"):
        return "general_runtime_error"
    if not general.get("completed", False):
        return "general_incomplete"
    fidelity = general.get("context_fidelity") or {}
    if fidelity.get("status") == "contradicted":
        return "general_context_contradicted"
    if fidelity.get("status") == "partially_supported":
        return "general_context_partial"
    if general.get("unsupported_fidelity_detail"):
        return "general_unsupported_interpretation"
    return "general_other"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tests/evaluation/v2_full_question_replay.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/v2_full_question_replay_v3_final.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cases = {item["id"]: item for item in manifest["cases"]}
    attempts: dict[str, list[dict]] = {identifier: [] for identifier in cases}
    for source_name, source_path in DEFAULT_SOURCES:
        path = Path(source_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        for result in payload["results"]:
            if result["id"] not in attempts:
                raise ValueError(f"unknown result id in {path}: {result['id']}")
            attempts[result["id"]].append({
                "source": source_name,
                "path": str(path),
                "result": result,
            })

    # Later files are deliberate controlled rechecks and supersede the first
    # stress run for only the ids they contain.
    merged = []
    for case in manifest["cases"]:
        available = attempts[case["id"]]
        if not available:
            raise ValueError(f"case has no live result: {case['id']}")
        selected = available[-1]
        result = {
            **selected["result"],
            "question": case["question"],
            "category": case["category"],
            "evaluation_mode": case["evaluation_mode"],
            "expected_contract": case["expected_contract"],
            "expectation_audit_note": case.get("expectation_audit_note"),
            "selected_source": selected["source"],
            "selected_source_path": selected["path"],
            "attempt_sources": [item["source"] for item in available],
        }
        # Rechecks were generated against the current audited manifest.  Make
        # the route predicate explicit instead of trusting a stale run1 flag.
        result["route_passed"] = (
            result.get("route_error") is None
            and result.get("actual_contract") == case["expected_contract"]
        )
        if not result["route_passed"]:
            result["passed"] = False
        result["failure_reason"] = failure_reason(result)
        merged.append(result)

    failure_counts = Counter(
        item["failure_reason"] for item in merged if item["failure_reason"]
    )
    category_summary = []
    for category in sorted({item["category"] for item in merged}):
        values = [item for item in merged if item["category"] == category]
        category_summary.append({
            "category": category,
            "total": len(values),
            "passed": sum(item["passed"] for item in values),
            "failed": sum(not item["passed"] for item in values),
        })
    summary = {
        "questions_total": len(merged),
        "questions_passed": sum(item["passed"] for item in merged),
        "questions_failed": sum(not item["passed"] for item in merged),
        "routing_passed": sum(item["route_passed"] for item in merged),
        "routing_total": len(merged),
        "contract_live_passed": sum(
            item["passed"] for item in merged
            if item["evaluation_mode"] == "contract_live"
        ),
        "contract_live_total": sum(
            item["evaluation_mode"] == "contract_live" for item in merged
        ),
        "general_agent_live_passed": sum(
            item["passed"] for item in merged
            if item["evaluation_mode"] == "general_agent_live"
        ),
        "general_agent_live_total": sum(
            item["evaluation_mode"] == "general_agent_live" for item in merged
        ),
        "failure_taxonomy": dict(sorted(failure_counts.items())),
    }
    projection = [
        {
            "id": item["id"],
            "passed": item["passed"],
            "route_passed": item["route_passed"],
            "actual_contract": item.get("actual_contract"),
            "failure_reason": item["failure_reason"],
            "selected_source": item["selected_source"],
        }
        for item in merged
    ]
    report = {
        "suite_id": manifest["suite_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": manifest["source_commit"],
        "manifest_sha256": sha256(manifest),
        "question_projection_sha256": manifest["question_projection_sha256"],
        "source_artifacts": [path for _, path in DEFAULT_SOURCES],
        "merge_policy": (
            "run1 covers all 61; infrastructure retry, default-240s budget, "
            "and audited-expectation rechecks supersede only named cases"
        ),
        "summary": summary,
        "category_summary": category_summary,
        "decision_projection_sha256": sha256(projection),
        "results": merged,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    print(f"decision projection {report['decision_projection_sha256']}")


if __name__ == "__main__":
    main()

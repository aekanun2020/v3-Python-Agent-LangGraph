"""Run a frozen question manifest against an unmodified external v2 checkout.

This adapter instruments EvidenceState.accept in memory.  It does not patch
the external repository and records only evidence that v2 itself admitted.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _completed(answer: str) -> bool:
    markers = (
        "หยุดตามขีดจำกัด",
        "ถึงขีดจำกัดขั้นตอน",
        "whole-run deadline",
        "runtime budget exhausted",
    )
    lowered = answer.casefold()
    return not any(marker.casefold() in lowered for marker in markers)


def _record_payload(record) -> dict:
    return {
        "evidence_id": record.evidence_id,
        "tool_name": record.tool_name,
        "arguments": record.arguments,
        "raw_result": record.raw_result,
        "result_hash": record.result_hash,
    }


def _git_commit(repository: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-repo", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=240)
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()

    v2_root = args.v2_repo.resolve()
    sys.path.insert(0, str(v2_root))

    from labs.core import config
    from labs.core.registry import ToolRegistry
    from labs.lab6_todo.agent_todo import run
    from labs.lab6_todo.evidence_contract import (
        contract_claims,
        select_metric_contract,
    )
    from labs.lab6_todo.evidence_state import EvidenceState

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    registry = ToolRegistry()
    discovered = registry.add_server(config.MCP_SERVER_URL)
    report = {
        "suite_id": "external-v2-runtime-63-question-replay",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "v2_repository": str(v2_root),
        "v2_commit": _git_commit(v2_root),
        "models": {
            "agent": config.OPENROUTER_MODEL,
            "observer": config.OBSERVER_MODEL,
        },
        "mcp_tools_discovered": discovered,
        "mcp_endpoint_recorded": False,
        "results": [],
    }

    original_accept = EvidenceState.accept
    try:
        for index, case in enumerate(manifest["cases"], start=1):
            accepted = []

            def capture_accept(state, record):
                before = len(state.records)
                original_accept(state, record)
                if len(state.records) > before:
                    accepted.append(record)

            EvidenceState.accept = capture_accept
            selected = select_metric_contract(case["question"])
            actual_contract = selected["id"] if selected else None
            stream = io.StringIO()
            error = None
            answer = ""
            started = time.monotonic()
            try:
                with contextlib.redirect_stdout(stream):
                    answer = run(
                        case["question"],
                        registry,
                        max_steps=12,
                        max_semantic_reviews=1,
                        max_mcp_calls=8,
                        max_dynamic_observations=4,
                        max_run_seconds=args.max_seconds,
                    ) or ""
            except Exception as caught:
                error = {
                    "type": type(caught).__name__,
                    "message": str(caught),
                }
            finally:
                EvidenceState.accept = original_accept

            evidence = EvidenceState()
            for record in accepted:
                original_accept(evidence, record)
            claims = (
                contract_claims(case["question"], evidence)
                if actual_contract
                else ()
            )
            result = {
                "id": case["id"],
                "question": case["question"],
                "category": case["category"],
                "expected_contract": case["expected_contract"],
                "actual_contract": actual_contract,
                "route_passed": actual_contract == case["expected_contract"],
                "answer": answer,
                "answer_nonempty": bool(answer.strip()),
                "completed": _completed(answer),
                "required_claims": list(claims),
                "accepted_evidence": [
                    _record_payload(record) for record in accepted
                ],
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "error": error,
                "stdout": stream.getvalue(),
            }
            report["results"].append(result)
            report["summary"] = {
                "questions_completed": len(report["results"]),
                "answers_nonempty": sum(
                    item["answer_nonempty"] for item in report["results"]
                ),
                "runtime_completed": sum(
                    item["completed"] for item in report["results"]
                ),
                "routing_matched_frozen_expectation": sum(
                    item["route_passed"] for item in report["results"]
                ),
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            if args.progress:
                print(
                    f"DONE {index}/{len(manifest['cases'])} {case['id']} "
                    f"route={actual_contract} evidence={len(accepted)}",
                    flush=True,
                )
    finally:
        EvidenceState.accept = original_accept
        registry.close()

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

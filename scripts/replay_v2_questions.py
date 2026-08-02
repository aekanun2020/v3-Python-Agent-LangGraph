"""Replay the frozen v2 question inventory against the current v3 runtime."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labs.core import config
from labs.core.registry import ToolRegistry
from labs.lab6_todo.agent_todo import dispatch_with_retry, run
from labs.lab6_todo.contract_router import (
    route_metric_contract,
    router_fingerprint,
)
from labs.lab6_todo.evidence_contract import (
    contract_claims,
    metric_contract_by_id,
    metric_contract_status,
)
from labs.lab6_todo.evidence_frame import (
    build_evidence_frame,
    reconcile_answer_with_context,
)
from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState


DEFAULT_MANIFEST = ROOT / "tests" / "evaluation" / "v2_full_question_replay.json"


def runtime_commit() -> str:
    """Return the exact v3 revision executed by the replay harness."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _answer_text(claims: tuple[str, ...]) -> str:
    if not claims:
        return ""
    return "ข้อเท็จจริงที่ผ่านการตรวจหลักฐาน:\n" + "\n".join(
        f"- {claim}" for claim in claims
    )


def _parse_fidelity(output: str) -> dict[str, Any] | None:
    match = re.search(
        r"\[CONTEXT FIDELITY\]\s+status=(\S+)\s+"
        r"frames=(\d+)/(\d+)\s+numeric_precision=([0-9.]+)\s+"
        r"label_recall=(\S+)\s+claim_recall=(\S+)",
        output,
    )
    if not match:
        return None

    def optional_number(value: str) -> float | None:
        return None if value == "None" else float(value)

    return {
        "status": match.group(1),
        "successful_frames": int(match.group(2)),
        "evidence_frames": int(match.group(3)),
        "numeric_precision": float(match.group(4)),
        "canonical_label_recall": optional_number(match.group(5)),
        "required_claim_recall": optional_number(match.group(6)),
    }


def _completed_answer(answer: str) -> bool:
    incomplete_markers = (
        "หยุดตามขีดจำกัด",
        "ถึงขีดจำกัดขั้นตอน",
        "whole-run deadline",
        "unresolved claims=",
        "runtime budget exhausted",
    )
    return not any(
        marker.casefold() in answer.casefold()
        for marker in incomplete_markers
    )


def _insufficient_specification(output: str) -> bool:
    """Recognize a deliberate pre-tool stop as a valid terminal outcome."""
    return "[REQUIREMENT GATE] verdict=insufficient_specification" in output


def _checkpoint(path: Path | None, report: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _contract_evidence(
    contract_id: str,
    registry: ToolRegistry,
) -> tuple[list[dict], str]:
    contract = metric_contract_by_id(contract_id)
    if contract is None:
        raise ValueError(f"unknown contract: {contract_id}")
    roles = []
    for role in contract["roles"]:
        query = role["query_template"]
        raw = dispatch_with_retry(
            registry,
            "execute_query_tool",
            {"query": query},
        )
        roles.append({
            "role_id": role["id"],
            "query": query,
            "result": raw,
        })
    return roles, sha256(roles)


def _evidence_state(case_id: str, roles: list[dict]) -> EvidenceState:
    evidence = EvidenceState()
    for role in roles:
        record = EvidenceRecord.from_tool(
            f"{case_id}:{role['role_id']}",
            "execute_query_tool",
            {"query": role["query"]},
            role["result"],
        )
        evidence.accept(record)
        evidence.add_frame(build_evidence_frame(record))
    return evidence


def _run_general(
    case: dict,
    registry: ToolRegistry,
    max_seconds: float,
) -> dict:
    stream = io.StringIO()
    started = time.monotonic()
    error = None
    answer = ""
    try:
        with contextlib.redirect_stdout(stream):
            answer = run(
                case["question"],
                registry,
                max_steps=12,
                max_semantic_reviews=1,
                max_mcp_calls=8,
                max_dynamic_observations=4,
                max_run_seconds=max_seconds,
                # Hybrid routing was already evaluated immediately before this
                # call and abstained.  Lexical mode avoids paying for the same
                # semantic routing decision twice; the downstream agent loop is
                # otherwise identical.
                contract_routing="lexical",
            ) or ""
    except Exception as caught:  # record and continue the full replay
        error = {
            "type": type(caught).__name__,
            "message": str(caught),
        }
    output = stream.getvalue()
    fidelity = _parse_fidelity(output)
    insufficient_specification = _insufficient_specification(output)
    route = re.search(
        r"\[CONTRACT ROUTING\].*?contract=(\S+)",
        output,
    )
    runtime_contract = None
    if route and route.group(1) not in {"None", "null"}:
        runtime_contract = route.group(1)
    fidelity_ok = bool(
        insufficient_specification
        or (
            fidelity
            and fidelity["status"] in {"supported", "insufficient_evidence"}
            and fidelity["numeric_precision"] == 1.0
        )
    )
    answer_ok = bool(answer.strip()) and answer.strip() not in {"None", "null"}
    unsupported_detail = "[CONTEXT FIDELITY DETAIL]" in output
    completed = _completed_answer(answer)
    passed = bool(
        error is None
        and runtime_contract is None
        and answer_ok
        and completed
        and fidelity_ok
        and not unsupported_detail
    )
    return {
        "passed": passed,
        "runtime_contract": runtime_contract,
        "answer": answer,
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "answer_nonempty": answer_ok,
        "completed": completed,
        "insufficient_specification": insufficient_specification,
        "context_fidelity": fidelity,
        "unsupported_fidelity_detail": unsupported_detail,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "error": error,
        "stdout": output,
    }


def replay(
    manifest: dict,
    *,
    output: Path | None,
    progress: bool,
    general_max_seconds: float,
) -> dict:
    if manifest.get("frozen_before_first_run") is not True:
        raise ValueError("manifest must be frozen before first run")
    registry = ToolRegistry()
    discovered = registry.add_server(config.MCP_SERVER_URL)
    report = {
        "suite_id": manifest["suite_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_commit": runtime_commit(),
        "source_commit": manifest["source_commit"],
        "manifest_sha256": sha256(manifest),
        "question_projection_sha256": manifest["question_projection_sha256"],
        "router_fingerprint": router_fingerprint(),
        "models": {
            "agent": config.OPENROUTER_MODEL,
            "router": config.ROUTER_MODEL,
            "observer": config.OBSERVER_MODEL,
        },
        "mcp_tools_discovered": discovered,
        "mcp_endpoint_recorded": False,
        "summary": {},
        "contract_evidence": {},
        "results": [],
    }
    cache: dict[str, tuple[list[dict], str]] = {}
    try:
        for index, case in enumerate(manifest["cases"], start=1):
            started = time.monotonic()
            route_error = None
            selected_contract = None
            try:
                decision = route_metric_contract(case["question"])
                actual_contract = decision.contract_id
                # Preserve question-owned typed bindings (for example >= 50%
                # versus the contract's default > 50%).  Reloading only by id
                # here silently discarded the router's admitted semantics and
                # made the replay measure a different contract than runtime.
                selected_contract = decision.contract
                route_detail = {
                    "path": decision.path.value,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    "semantic_attempted": decision.semantic_attempted,
                }
            except Exception as error:
                actual_contract = None
                route_error = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
                route_detail = None
            route_passed = (
                route_error is None
                and actual_contract == case["expected_contract"]
            )
            result = {
                "id": case["id"],
                "question": case["question"],
                "category": case["category"],
                "evaluation_mode": case["evaluation_mode"],
                "expected_contract": case["expected_contract"],
                "actual_contract": actual_contract,
                "route_passed": route_passed,
                "route": route_detail,
                "route_error": route_error,
                "passed": False,
            }
            if case["evaluation_mode"] == "contract_live":
                if route_passed and actual_contract:
                    if actual_contract not in cache:
                        try:
                            cache[actual_contract] = _contract_evidence(
                                actual_contract,
                                registry,
                            )
                            roles, evidence_hash = cache[actual_contract]
                            report["contract_evidence"][actual_contract] = {
                                "evidence_sha256": evidence_hash,
                                "roles": roles,
                            }
                        except Exception as error:
                            result["contract_error"] = {
                                "type": type(error).__name__,
                                "message": str(error),
                            }
                    if actual_contract in cache:
                        roles, evidence_hash = cache[actual_contract]
                        evidence = _evidence_state(case["id"], roles)
                        contract = selected_contract
                        status = metric_contract_status(
                            case["question"],
                            evidence,
                            contract=contract,
                        )
                        claims = contract_claims(
                            case["question"],
                            evidence,
                            contract=contract,
                        )
                        answer = _answer_text(claims)
                        fidelity = reconcile_answer_with_context(
                            case["question"],
                            answer,
                            evidence,
                            required_claims=claims,
                        )
                        result["contract"] = {
                            "evidence_sha256": evidence_hash,
                            "satisfied": status.satisfied,
                            "missing_roles": list(status.missing_roles),
                            "claim_count": len(claims),
                            "claims": list(claims),
                            "answer_sha256": hashlib.sha256(
                                answer.encode("utf-8")
                            ).hexdigest(),
                            "context_fidelity": fidelity.to_dict(),
                        }
                        result["passed"] = bool(
                            status.satisfied
                            and claims
                            and fidelity.status == "supported"
                            and fidelity.numeric_precision == 1.0
                            and fidelity.required_claim_recall == 1.0
                        )
            else:
                if route_passed:
                    general = _run_general(
                        case,
                        registry,
                        general_max_seconds,
                    )
                    result["general"] = general
                    result["passed"] = general["passed"]
            result["elapsed_seconds"] = round(
                time.monotonic() - started,
                6,
            )
            report["results"].append(result)
            summary = {
                "questions_total": len(report["results"]),
                "questions_passed": sum(
                    item["passed"] for item in report["results"]
                ),
                "questions_failed": sum(
                    not item["passed"] for item in report["results"]
                ),
                "routing_passed": sum(
                    item["route_passed"] for item in report["results"]
                ),
                "contract_live_passed": sum(
                    item["passed"]
                    for item in report["results"]
                    if item["evaluation_mode"] == "contract_live"
                ),
                "contract_live_total": sum(
                    item["evaluation_mode"] == "contract_live"
                    for item in report["results"]
                ),
                "general_agent_live_passed": sum(
                    item["passed"]
                    for item in report["results"]
                    if item["evaluation_mode"] == "general_agent_live"
                ),
                "general_agent_live_total": sum(
                    item["evaluation_mode"] == "general_agent_live"
                    for item in report["results"]
                ),
            }
            report["summary"] = summary
            _checkpoint(output, report)
            if progress:
                marker = "PASS" if result["passed"] else "FAIL"
                print(
                    f"{marker} {index}/{manifest['question_count']} "
                    f"{case['id']} mode={case['evaluation_mode']} "
                    f"expected={case['expected_contract']} "
                    f"actual={actual_contract}",
                    flush=True,
                )
    finally:
        registry.close()
    projection = [
        {
            "id": item["id"],
            "passed": item["passed"],
            "route_passed": item["route_passed"],
            "actual_contract": item["actual_contract"],
            "answer_sha256": (
                item.get("contract", {}).get("answer_sha256")
                or item.get("general", {}).get("answer_sha256")
            ),
        }
        for item in report["results"]
    ]
    report["decision_projection_sha256"] = sha256(projection)
    _checkpoint(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--allow-failures", action="store_true")
    parser.add_argument("--general-max-seconds", type=float, default=180)
    parser.add_argument(
        "--case-id",
        action="append",
        help="replay only this case id; repeat for multiple cases",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.case_id:
        selected = set(args.case_id)
        available = {item["id"] for item in manifest["cases"]}
        missing = selected - available
        if missing:
            parser.error("unknown case ids: " + ", ".join(sorted(missing)))
        manifest = {
            **manifest,
            "cases": [
                item for item in manifest["cases"] if item["id"] in selected
            ],
            "question_count": len(selected),
        }
    report = replay(
        manifest,
        output=args.output,
        progress=args.progress,
        general_max_seconds=args.general_max_seconds,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"decision projection {report['decision_projection_sha256']}")
    if report["summary"]["questions_failed"] and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

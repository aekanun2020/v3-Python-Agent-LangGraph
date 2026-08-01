"""Replay named v2 incidents against the current v3 runtime.

Offline checks prove removed paths, deterministic gates, and frozen unit
regressions. ``--live`` additionally calls the configured semantic router and
MSSQL MCP, so provider/tool availability is kept separate from code behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labs.core import config
from labs.core.registry import ToolRegistry
from labs.lab6_todo.contract_router import (
    route_metric_contract,
    router_fingerprint,
    validate_semantic_proposal,
)
from labs.lab6_todo.evidence_contract import (
    contract_claims,
    metric_contract_by_id,
    metric_contract_status,
)
from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState


DEFAULT_MANIFEST = ROOT / "tests" / "evaluation" / "v2_incidents.json"


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_unit_tests(names: list[str]) -> tuple[bool, dict]:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(names)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    return result.wasSuccessful(), {
        "tests_run": result.testsRun,
        "failures": [test.id() for test, _ in result.failures],
        "errors": [test.id() for test, _ in result.errors],
        "runner_output": stream.getvalue().strip(),
    }


def _source_absence(check: dict) -> tuple[bool, dict]:
    existing = [
        path for value in check.get("paths_must_not_exist", ())
        if (path := ROOT / value).exists()
    ]
    matches: list[dict] = []
    patterns = [re.compile(value) for value in check["forbidden_patterns"]]
    for relative in check.get("search_paths", ()):
        base = ROOT / relative
        candidates = [base] if base.is_file() else sorted(base.rglob("*.py"))
        for path in candidates:
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                if pattern.search(text):
                    matches.append({
                        "path": str(path.relative_to(ROOT)),
                        "pattern": pattern.pattern,
                    })
    return not existing and not matches, {
        "unexpected_existing_paths": [
            str(path.relative_to(ROOT)) for path in existing
        ],
        "forbidden_matches": matches,
    }


def _offline_route(check: dict) -> tuple[bool, dict]:
    proposal = check.get("semantic_proposal")
    if proposal is not None:
        decision = validate_semantic_proposal(check["question"], proposal)
    else:
        decision = route_metric_contract(check["question"], semantic=False)
    actual = decision.contract_id
    return actual == check["expected_contract"], {
        "expected_contract": check["expected_contract"],
        "actual_contract": actual,
        "path": decision.path.value,
        "reason": decision.reason,
    }


def _live_routes(check: dict, repeat: int) -> tuple[bool, dict]:
    attempts = []
    for index in range(1, repeat + 1):
        started = time.monotonic()
        try:
            decision = route_metric_contract(check["question"])
            attempts.append({
                "attempt": index,
                "actual_contract": decision.contract_id,
                "path": decision.path.value,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "semantic_attempted": decision.semantic_attempted,
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "passed": decision.contract_id == check["expected_contract"],
            })
        except Exception as error:  # provider failure is a replay failure
            attempts.append({
                "attempt": index,
                "actual_contract": None,
                "error_type": type(error).__name__,
                "error": str(error),
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "passed": False,
            })
    return all(item["passed"] for item in attempts), {
        "expected_contract": check["expected_contract"],
        "attempts": attempts,
        "stable_projection": len({
            (item.get("actual_contract"), item.get("path"))
            for item in attempts
        }) == 1,
    }


def _live_contract(
    incident_id: str,
    check: dict,
    registry: ToolRegistry,
) -> tuple[bool, dict]:
    contract = metric_contract_by_id(check["expected_contract"])
    if contract is None:
        return False, {"error": "unknown expected contract"}
    evidence = EvidenceState()
    roles = []
    started = time.monotonic()
    try:
        for role in contract["roles"]:
            query = role["query_template"]
            raw = registry.dispatch("execute_query_tool", {"query": query})
            evidence.accept(EvidenceRecord.from_tool(
                f"{incident_id}:{role['id']}",
                "execute_query_tool",
                {"query": query},
                raw,
            ))
            roles.append({
                "role_id": role["id"],
                "query": query,
                "result": raw,
            })
        status = metric_contract_status(
            check["question"],
            evidence,
            contract=contract,
        )
        claims = contract_claims(
            check["question"],
            evidence,
            contract=contract,
        )
        answer = "\n".join(claims)
        required = {
            pattern: bool(re.search(pattern, answer, flags=re.IGNORECASE))
            for pattern in check.get("required_claim_patterns", ())
        }
        forbidden = {
            pattern: bool(re.search(pattern, answer, flags=re.IGNORECASE))
            for pattern in check.get("forbidden_claim_patterns", ())
        }
        expected_verdict = check.get("expected_terminal_verdict")
        actual_verdict = contract.get("terminal_verdict", "approve")
        passed = (
            status.satisfied
            and bool(claims)
            and all(required.values())
            and not any(forbidden.values())
            and (
                expected_verdict is None
                or actual_verdict == expected_verdict
            )
        )
        return passed, {
            "contract_id": contract["id"],
            "satisfied": status.satisfied,
            "missing_roles": list(status.missing_roles),
            "terminal_verdict": actual_verdict,
            "claims": list(claims),
            "required_pattern_matches": required,
            "forbidden_pattern_matches": forbidden,
            "roles": roles,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
    except Exception as error:
        return False, {
            "error_type": type(error).__name__,
            "error": str(error),
            "roles": roles,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }


def replay(
    manifest: dict,
    *,
    live: bool,
    repeat: int,
    progress: bool,
) -> dict:
    results = []
    registry = None
    discovered = []
    if live:
        registry = ToolRegistry()
        discovered = registry.add_server(config.MCP_SERVER_URL)
    try:
        for incident in manifest["incidents"]:
            check = incident["check"]
            check_type = check["type"]
            if check_type == "source_absence":
                offline_passed, offline = _source_absence(check)
            elif check_type == "unit_tests":
                offline_passed, offline = _run_unit_tests(check["tests"])
            elif check_type in {"route_only", "route_and_contract"}:
                offline_passed, offline = _offline_route(check)
            else:
                raise ValueError(f"unknown incident check type: {check_type}")

            live_passed = None
            live_detail = None
            contract_passed = None
            contract_detail = None
            if live and check_type in {"route_only", "route_and_contract"}:
                live_passed, live_detail = _live_routes(check, repeat)
            if (
                live
                and check.get("execute_live_contract")
                and check["expected_contract"] is not None
            ):
                assert registry is not None
                contract_passed, contract_detail = _live_contract(
                    incident["id"], check, registry
                )

            passed = offline_passed
            if live_passed is not None:
                passed = passed and live_passed
            if contract_passed is not None:
                passed = passed and contract_passed
            result = {
                **{key: incident[key] for key in (
                    "id", "historical_symptom", "layer", "disposition"
                )},
                "check_type": check_type,
                "passed": passed,
                "offline_passed": offline_passed,
                "offline": offline,
                "live_routing_passed": live_passed,
                "live_routing": live_detail,
                "live_contract_passed": contract_passed,
                "live_contract": contract_detail,
            }
            results.append(result)
            if progress:
                marker = "PASS" if passed else "FAIL"
                print(f"{marker} {incident['id']} ({check_type})", flush=True)
    finally:
        if registry is not None:
            registry.close()

    live_routes = [
        attempt
        for item in results
        if item["live_routing"]
        for attempt in item["live_routing"]["attempts"]
    ]
    live_contracts = [
        item for item in results if item["live_contract_passed"] is not None
    ]
    projection = [
        {
            "id": item["id"],
            "passed": item["passed"],
            "offline_passed": item["offline_passed"],
            "live_routes": [
                attempt.get("actual_contract")
                for attempt in (item["live_routing"] or {}).get("attempts", ())
            ],
            "live_contract_passed": item["live_contract_passed"],
        }
        for item in results
    ]
    return {
        "suite_id": manifest["suite_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": _sha256(manifest),
        "router_fingerprint": router_fingerprint(),
        "mode": "live" if live else "offline",
        "live_router_repeats": repeat if live else 0,
        "mcp_tools_discovered": discovered,
        "summary": {
            "incidents_total": len(results),
            "incidents_passed": sum(item["passed"] for item in results),
            "incidents_failed": sum(not item["passed"] for item in results),
            "not_applicable_by_removal": sum(
                item["disposition"] == "not_applicable_by_removal"
                for item in results
            ),
            "live_routing_attempts": len(live_routes),
            "live_routing_passed": sum(item["passed"] for item in live_routes),
            "live_contracts_total": len(live_contracts),
            "live_contracts_passed": sum(
                item["live_contract_passed"] for item in live_contracts
            ),
        },
        "decision_projection_sha256": _sha256(projection),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--allow-failures", action="store_true")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("frozen_before_first_run") is not True:
        parser.error("incident manifest must be frozen before first run")
    report = replay(
        manifest,
        live=args.live,
        repeat=args.repeat,
        progress=args.progress,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"decision projection {report['decision_projection_sha256']}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.output}")
    if report["summary"]["incidents_failed"] and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

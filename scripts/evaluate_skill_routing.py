"""Evaluate frozen unseen paraphrases and boundary cases."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labs.core import config
from labs.core.registry import ToolRegistry
from labs.lab6_todo.evidence_contract import (
    contract_claims,
    metric_contract_by_id,
    metric_contract_status,
    select_metric_contract,
)
from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState
from labs.lab6_todo.contract_router import (
    route_metric_contract,
    router_fingerprint,
)


SUITE_DIR = ROOT / "tests" / "evaluation"
SUITE_FILES = (
    "hr_unseen_paraphrases.json",
    "hr_boundaries.json",
    "finance_unseen_paraphrases.json",
    "finance_boundaries.json",
)
CORRECTIONS_FILE = SUITE_DIR / "semantic_v2_corrections.json"
V3_CORRECTIONS_FILE = SUITE_DIR / "semantic_v3_corrections.json"


def _apply_corrections(cases: list[dict], path: Path) -> None:
    corrections = json.loads(path.read_text(encoding="utf-8"))
    if corrections.get("frozen_before_first_run") is not True:
        raise ValueError(f"corrections are not frozen: {path.name}")
    by_id = {item["id"]: item for item in cases}
    for correction in corrections["corrections"]:
        identifier = correction["id"]
        if identifier not in by_id:
            raise ValueError(f"correction names unknown case: {identifier}")
        previous = by_id[identifier].get("suite_corrections", ())
        by_id[identifier].update({
            "question": correction["question"],
            "expected_contract": correction["expected_contract"],
            "suite_corrections": [
                *previous,
                correction["reason"],
            ],
        })


def load_cases(suite_version: str = "semantic-v3") -> list[dict]:
    cases: list[dict] = []
    for name in SUITE_FILES:
        payload = json.loads((SUITE_DIR / name).read_text(encoding="utf-8"))
        if payload.get("frozen_before_first_run") is not True:
            raise ValueError(f"suite is not frozen: {name}")
        kind = "boundary" if "boundaries" in name else "paraphrase"
        domain = "hr" if name.startswith("hr_") else "finance"
        for item in payload["cases"]:
            cases.append({**item, "kind": kind, "domain": domain})
    if suite_version == "frozen-v1":
        return cases
    if suite_version not in {"semantic-v2", "semantic-v3"}:
        raise ValueError(f"unknown suite version: {suite_version}")
    _apply_corrections(cases, CORRECTIONS_FILE)
    if suite_version == "semantic-v3":
        _apply_corrections(cases, V3_CORRECTIONS_FILE)
    return cases


def evaluate_routing(
    cases: list[dict],
    routing_mode: str = "legacy",
    workers: int = 1,
    progress: bool = False,
) -> tuple[list[dict], dict]:
    def evaluate_one(item: dict) -> dict:
        started = time.monotonic()
        if routing_mode == "hybrid":
            decision = route_metric_contract(item["question"])
            actual = decision.contract_id
            routing_details = {
                "routing_path": decision.path.value,
                "routing_confidence": decision.confidence,
                "routing_reason": decision.reason,
                "term_evidence": dict(decision.term_evidence),
                "semantic_attempted": decision.semantic_attempted,
            }
        else:
            selected = select_metric_contract(item["question"])
            actual = selected["id"] if selected else None
            routing_details = {
                "routing_path": "legacy-literal",
                "routing_confidence": 1.0 if selected else 0.0,
                "routing_reason": "legacy question_terms_all/any",
                "term_evidence": {},
                "semantic_attempted": False,
            }
        passed = actual == item["expected_contract"]
        return {
            **item,
            "actual_contract": actual,
            "passed": passed,
            "routing_elapsed_seconds": round(
                time.monotonic() - started,
                6,
            ),
            **routing_details,
        }

    if workers <= 1:
        results = []
        for index, item in enumerate(cases, 1):
            result = evaluate_one(item)
            results.append(result)
            if progress:
                print(
                    f"ROUTED {index}/{len(cases)} {item['id']} "
                    f"path={result['routing_path']}",
                    flush=True,
                )
    else:
        indexed_results: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(evaluate_one, item): (index, item)
                for index, item in enumerate(cases)
            }
            completed = 0
            for future in as_completed(futures):
                index, item = futures[future]
                indexed_results[index] = future.result()
                completed += 1
                if progress:
                    print(
                        f"ROUTED {completed}/{len(cases)} {item['id']} "
                        f"path={indexed_results[index]['routing_path']}",
                        flush=True,
                    )
        # Evaluation output remains stable even though provider calls overlap.
        results = [indexed_results[index] for index in range(len(cases))]

    paraphrases = [item for item in results if item["kind"] == "paraphrase"]
    boundaries = [item for item in results if item["kind"] == "boundary"]
    recall_hits = sum(item["passed"] for item in paraphrases)
    protected = sum(item["passed"] for item in boundaries)
    negative_boundaries = [
        item for item in boundaries if item["expected_contract"] is None
    ]
    false_matches = sum(
        item["actual_contract"] is not None for item in negative_boundaries
    )
    missed_safe_routes = sum(
        not item["passed"]
        for item in boundaries
        if item["expected_contract"] is not None
    )
    routing_latencies = [item["routing_elapsed_seconds"] for item in results]
    semantic_latencies = [
        item["routing_elapsed_seconds"]
        for item in results
        if item["semantic_attempted"]
    ]

    def percentile_95(values: list[float]) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = max(0, math.ceil(0.95 * len(ordered)) - 1)
        return round(ordered[index], 6)

    metrics = {
        "paraphrases_total": len(paraphrases),
        "paraphrases_correct": recall_hits,
        "contract_recall": (
            recall_hits / len(paraphrases) if paraphrases else None
        ),
        "boundaries_total": len(boundaries),
        "boundaries_protected": protected,
        "boundary_accuracy": (
            protected / len(boundaries) if boundaries else None
        ),
        # Retained for consumers of the frozen-v1 report. These are near-
        # boundary cases, so accuracy is the statistically correct name.
        "boundary_precision": (
            protected / len(boundaries) if boundaries else None
        ),
        "false_matches": false_matches,
        "false_match_rate": (
            false_matches / len(negative_boundaries)
            if negative_boundaries else None
        ),
        "missed_safe_boundary_routes": missed_safe_routes,
        "lexical_routes": sum(
            item["routing_path"] == "lexical" for item in results
        ),
        "semantic_routes": sum(
            item["routing_path"] == "semantic" for item in results
        ),
        "semantic_attempts": sum(
            item["semantic_attempted"] for item in results
        ),
        "abstentions": sum(
            item["routing_path"] == "abstain" for item in results
        ),
        "routing_median_seconds": (
            round(statistics.median(routing_latencies), 6)
            if routing_latencies else None
        ),
        "semantic_median_seconds": (
            round(statistics.median(semantic_latencies), 6)
            if semantic_latencies else None
        ),
        "semantic_p95_seconds": percentile_95(semantic_latencies),
    }
    return results, metrics


def evaluate_live(routing_results: list[dict]) -> list[dict]:
    representatives: dict[str, dict] = {}
    for item in routing_results:
        if (
            item["kind"] == "paraphrase"
            and item["passed"]
            and item["actual_contract"]
        ):
            representatives.setdefault(item["actual_contract"], item)

    registry = ToolRegistry()
    discovered = registry.add_server(config.MCP_SERVER_URL)
    live_results = []
    try:
        for contract_id, item in representatives.items():
            contract = metric_contract_by_id(contract_id)
            if contract is None:
                raise ValueError(f"unknown routed contract: {contract_id}")
            evidence = EvidenceState()
            started = time.monotonic()
            role_results = []
            for role in contract["roles"]:
                query = role["query_template"]
                raw = registry.dispatch("execute_query_tool", {"query": query})
                evidence.accept(EvidenceRecord.from_tool(
                    f"{item['id']}:{role['id']}",
                    "execute_query_tool",
                    {"query": query},
                    raw,
                ))
                role_results.append({
                    "role_id": role["id"],
                    "query": query,
                    "result": raw,
                })
            status = metric_contract_status(
                item["question"],
                evidence,
                contract=contract,
            )
            emitted_claims = contract_claims(
                item["question"],
                evidence,
                contract=contract,
            )
            live_results.append({
                "case_id": item["id"],
                "contract_id": contract_id,
                "mcp_tools_discovered": discovered,
                "satisfied": status.satisfied,
                "answer_complete": bool(emitted_claims),
                "emitted_claim_count": len(emitted_claims),
                "emitted_claims": list(emitted_claims),
                "missing_roles": list(status.missing_roles),
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "roles": role_results,
            })
    finally:
        registry.close()
    return live_results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--routing-mode",
        choices=["legacy", "hybrid"],
        default="hybrid",
    )
    parser.add_argument(
        "--suite-version",
        choices=["frozen-v1", "semantic-v2", "semantic-v3"],
        default="semantic-v3",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="parallel semantic-router requests for evaluation only",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="print one progress line as each routing case finishes",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        help="evaluate only the named case; repeat for multiple cases",
    )
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="write an exploratory/baseline report without a failing exit",
    )
    args = parser.parse_args()

    cases = load_cases(args.suite_version)
    if args.case_id:
        selected_ids = set(args.case_id)
        cases = [item for item in cases if item["id"] in selected_ids]
        missing_ids = selected_ids - {item["id"] for item in cases}
        if missing_ids:
            parser.error("unknown case ids: " + ", ".join(sorted(missing_ids)))
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    routing, metrics = evaluate_routing(
        cases,
        args.routing_mode,
        workers=args.workers,
        progress=args.progress,
    )
    live = evaluate_live(routing) if args.live else []
    normalized_live = [
        {
            "contract_id": item["contract_id"],
            "satisfied": item["satisfied"],
            "answer_complete": item["answer_complete"],
            "emitted_claim_count": item["emitted_claim_count"],
            "missing_roles": item["missing_roles"],
            "roles": item["roles"],
        }
        for item in live
    ]
    live_evidence_hash = (
        hashlib.sha256(
            json.dumps(
                normalized_live,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if live else None
    )
    report = {
        "suite_version": args.suite_version,
        "selector": args.routing_mode,
        "router_fingerprint": (
            router_fingerprint() if args.routing_mode == "hybrid" else None
        ),
        "metrics": metrics,
        "routing_results": routing,
        "live_results": live,
        "live_evidence_hash": live_evidence_hash,
        "live_contract_completion": (
            sum(item["satisfied"] for item in live) / len(live)
            if live else None
        ),
        "live_answer_completion": (
            sum(item["answer_complete"] for item in live) / len(live)
            if live else None
        ),
    }

    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    for item in routing:
        marker = "PASS" if item["passed"] else "FAIL"
        print(
            f"{marker} {item['id']}: expected={item['expected_contract']} "
            f"actual={item['actual_contract']}"
        )
    if live:
        passed = sum(item["satisfied"] for item in live)
        print(f"LIVE {passed}/{len(live)} contracts complete")
        answers = sum(item["answer_complete"] for item in live)
        print(f"LIVE {answers}/{len(live)} answers non-empty")
        print(f"LIVE evidence hash {live_evidence_hash}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.output}")

    routing_failed = any(not item["passed"] for item in routing)
    live_failed = any(
        not item["satisfied"] or not item["answer_complete"]
        for item in live
    )
    if (routing_failed or live_failed) and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

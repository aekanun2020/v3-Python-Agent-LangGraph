"""Score captured v2 answers with v3's evidence-context fidelity checker."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labs.lab6_todo.evidence_frame import (
    build_evidence_frame,
    reconcile_answer_with_context,
)
from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    for item in report["results"]:
        evidence = EvidenceState()
        for raw in item["accepted_evidence"]:
            record = EvidenceRecord.from_tool(
                raw["evidence_id"],
                raw["tool_name"],
                raw["arguments"],
                raw["raw_result"],
            )
            evidence.accept(record)
            evidence.add_frame(build_evidence_frame(record))
        fidelity = reconcile_answer_with_context(
            item["question"],
            item["answer"],
            evidence,
            required_claims=tuple(item["required_claims"]),
        )
        item["context_fidelity"] = fidelity.to_dict()
        item["evidence_passed"] = bool(
            item["error"] is None
            and item["answer_nonempty"]
            and item["completed"]
            and fidelity.status in {"supported", "insufficient_evidence"}
            and fidelity.numeric_precision == 1.0
            and not fidelity.unsupported_interpretations
            and (
                not item["required_claims"]
                or fidelity.required_claim_recall == 1.0
            )
        )
        item["passed"] = bool(item["route_passed"] and item["evidence_passed"])

    report["scored_summary"] = {
        "questions_total": len(report["results"]),
        "questions_passed": sum(item["passed"] for item in report["results"]),
        "questions_failed": sum(not item["passed"] for item in report["results"]),
        "routing_passed": sum(
            item["route_passed"] for item in report["results"]
        ),
        "evidence_answers_passed": sum(
            item["evidence_passed"] for item in report["results"]
        ),
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["scored_summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

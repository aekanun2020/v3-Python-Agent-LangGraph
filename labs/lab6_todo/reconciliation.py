"""Selective, deterministic reconciliation for quantitative tool results.

The runtime does not ask an LLM to judge whether two query results agree.
For a calculation-heavy primary result, it asks the agent for an independent
query with the same output contract, then compares the two tabular frames.
"""
from __future__ import annotations

import json
import hashlib
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from labs.lab6_todo.evidence_frame import EvidenceFrame
from labs.lab6_todo.risk_router import DeterministicObservation


class ReconciliationVerdict(str, Enum):
    NOT_REQUIRED = "not_required"
    VERIFY = "verify"
    MATCH = "match"
    CONFLICT = "conflict"
    INVALID_VERIFICATION = "invalid_verification"


@dataclass(frozen=True)
class ReconciliationRequest:
    primary_evidence_id: str
    risk_reasons: tuple[str, ...]
    expected_fields: tuple[str, ...]
    instruction: str


@dataclass(frozen=True)
class ReconciliationResult:
    primary_evidence_id: str
    verification_evidence_id: str
    verdict: ReconciliationVerdict
    reason: str
    expected_fields: tuple[str, ...]
    primary_row_count: int
    verification_row_count: int

    @property
    def matched(self) -> bool:
        return self.verdict is ReconciliationVerdict.MATCH

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verdict"] = self.verdict.value
        return payload


RECONCILABLE_RISKS = frozenset({
    "distinct-grain",
    "multi-source",
    "derived-ratio",
    "conditional-metric",
    "aggregate-comparison",
})


def needs_reconciliation(
    observation: DeterministicObservation,
    frame: EvidenceFrame,
) -> bool:
    """Route only successful quantitative tabular results to verification."""
    return (
        observation.action_succeeded
        and observation.decision.value == "accept"
        and frame.result_kind == "tabular"
        and bool(frame.rows)
        and bool(
            frame.aggregations
            or RECONCILABLE_RISKS.intersection(observation.risk_reasons)
        )
    )


def build_reconciliation_request(
    observation: DeterministicObservation,
    frame: EvidenceFrame,
) -> ReconciliationRequest:
    fields = ", ".join(frame.fields)
    reasons = tuple(
        reason for reason in observation.risk_reasons
        if reason in RECONCILABLE_RISKS
    )
    if frame.aggregations and not reasons:
        reasons = ("aggregate-result",)
    instruction = (
        "verify: run one independent read-only query for the same population, "
        "filters, grain and metric. Use a materially different SQL calculation "
        "or query shape, but return exactly the same output columns and aliases "
        f"in this order: {fields}. Do not copy the previous SQL. The runtime "
        "will compare rows and numeric values deterministically."
    )
    return ReconciliationRequest(
        primary_evidence_id=frame.evidence_id,
        risk_reasons=reasons,
        expected_fields=frame.fields,
        instruction=instruction,
    )


def _normalized_sql(query: str) -> str:
    without_comments = re.sub(r"--.*?$|/\*.*?\*/", " ", query, flags=re.M | re.S)
    return " ".join(without_comments.casefold().split())


def _canonical_value(value: Any) -> tuple[str, Any]:
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("number", float(value))
    if value is None:
        return ("null", None)
    return ("text", str(value))


def _row_signature(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    values = [_canonical_value(row[field]) for field in fields]
    # Numbers are rounded only to absorb harmless transport formatting noise.
    normalized = [
        (kind, round(value, 9)) if kind == "number" else (kind, value)
        for kind, value in values
    ]
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def result_fingerprint(frame: EvidenceFrame) -> str:
    """Identify one output contract + row multiset, independent of SQL/order."""
    payload = json.dumps({
        "fields": frame.fields,
        "rows": sorted(
            _row_signature(row, frame.fields)
            for row in frame.row_dicts()
        ),
    }, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _rows_match(
    primary: tuple[dict[str, Any], ...],
    verification: tuple[dict[str, Any], ...],
    fields: tuple[str, ...],
) -> bool:
    if len(primary) != len(verification):
        return False
    # Fast exact/canonical multiset comparison, independent of row order.
    if Counter(_row_signature(row, fields) for row in primary) == Counter(
        _row_signature(row, fields) for row in verification
    ):
        return True
    # A narrow numeric-tolerance fallback keeps labels and nulls exact.
    def sort_key(row: dict[str, Any]) -> str:
        non_numeric = [
            (field, value)
            for field, value in row.items()
            if not isinstance(value, (int, float)) or isinstance(value, bool)
        ]
        return json.dumps(non_numeric, ensure_ascii=False, default=str)

    left = sorted(primary, key=sort_key)
    right = sorted(verification, key=sort_key)
    for left_row, right_row in zip(left, right):
        for field in fields:
            left_value = left_row[field]
            right_value = right_row[field]
            numeric = (
                isinstance(left_value, (int, float))
                and not isinstance(left_value, bool)
                and isinstance(right_value, (int, float))
                and not isinstance(right_value, bool)
            )
            if numeric:
                if not math.isclose(
                    float(left_value),
                    float(right_value),
                    rel_tol=1e-9,
                    abs_tol=1e-6,
                ):
                    return False
            elif left_value != right_value:
                return False
    return True


def reconcile_frames(
    primary: EvidenceFrame,
    verification: EvidenceFrame,
) -> ReconciliationResult:
    """Compare independent evidence under the primary output contract."""
    base = {
        "primary_evidence_id": primary.evidence_id,
        "verification_evidence_id": verification.evidence_id,
        "expected_fields": primary.fields,
        "primary_row_count": len(primary.rows),
        "verification_row_count": len(verification.rows),
    }
    if not verification.action_succeeded or verification.result_kind != "tabular":
        return ReconciliationResult(
            **base,
            verdict=ReconciliationVerdict.INVALID_VERIFICATION,
            reason="verification did not return a successful tabular result",
        )
    if verification.fields != primary.fields:
        return ReconciliationResult(
            **base,
            verdict=ReconciliationVerdict.INVALID_VERIFICATION,
            reason=(
                "verification output contract differs: expected "
                f"{list(primary.fields)}, got {list(verification.fields)}"
            ),
        )
    if not primary.query or not verification.query:
        return ReconciliationResult(
            **base,
            verdict=ReconciliationVerdict.INVALID_VERIFICATION,
            reason="both primary and verification evidence require SQL text",
        )
    if _normalized_sql(primary.query) == _normalized_sql(verification.query):
        return ReconciliationResult(
            **base,
            verdict=ReconciliationVerdict.INVALID_VERIFICATION,
            reason="verification repeated the primary SQL",
        )
    matched = _rows_match(
        primary.row_dicts(),
        verification.row_dicts(),
        primary.fields,
    )
    return ReconciliationResult(
        **base,
        verdict=(
            ReconciliationVerdict.MATCH
            if matched
            else ReconciliationVerdict.CONFLICT
        ),
        reason=(
            "independent query returned the same rows and values"
            if matched
            else "independent query returned conflicting rows or values"
        ),
    )

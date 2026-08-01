"""Deterministic tool-context frames and answer-fidelity measurements.

The frame is intentionally domain-neutral.  Skills and executable contracts
may add meaning later, but the runtime first records exactly what the tool
returned: fields, rows, filters, grouping, labels, and numeric values.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState


ERROR_MARKERS = (
    '"status": "error"',
    "'status': 'error'",
    "traceback (most recent call last)",
    "syntax error",
    "invalid object name",
    "connection error",
    "timeout",
)
EMPTY_MARKERS = (
    "no results",
    "no rows",
    "empty result",
    "0 rows",
)


@dataclass(frozen=True)
class EvidenceFrame:
    evidence_id: str
    tool_name: str
    action_succeeded: bool
    result_kind: str
    fields: tuple[str, ...]
    rows: tuple[tuple[tuple[str, Any], ...], ...]
    query: str
    filters: tuple[str, ...]
    group_by: tuple[str, ...]
    aggregations: tuple[str, ...]
    grain: str
    canonical_labels: tuple[str, ...]
    numeric_values: tuple[str, ...]
    result_hash: str

    def row_dicts(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(row) for row in self.rows)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rows"] = list(self.row_dicts())
        return payload


@dataclass(frozen=True)
class ContextFidelityReport:
    status: str
    evidence_frames: int
    successful_frames: int
    numeric_precision: float
    canonical_label_recall: float | None
    required_claim_recall: float | None
    unsupported_numbers: tuple[str, ...]
    unsupported_interpretations: tuple[str, ...]
    missing_labels: tuple[str, ...]
    missing_claims: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return self.status == "supported"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _query_text(record: EvidenceRecord) -> str:
    for key in ("query", "sql", "statement"):
        value = record.arguments.get(key)
        if isinstance(value, str):
            return value
    return ""


def _parse_value(value: str) -> Any:
    stripped = value.strip()
    if stripped.casefold() in {"null", "none", "nan"}:
        return None
    compact = stripped.replace(",", "")
    if re.fullmatch(r"[-+]?\d+", compact):
        try:
            return int(compact)
        except ValueError:
            pass
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)", compact):
        try:
            return float(compact)
        except ValueError:
            pass
    return stripped


def _tabular_rows(raw_result: str) -> tuple[tuple[str, ...], tuple[dict, ...]]:
    lines = [line.rstrip() for line in raw_result.splitlines() if line.strip()]
    if len(lines) < 2:
        return (), ()
    fields = tuple(
        value.strip()
        for value in re.split(r"\s{2,}|\t+", lines[0].strip())
        if value.strip()
    )
    if not fields or any(
        not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.$]*", field)
        for field in fields
    ):
        return (), ()
    rows = []
    for line in lines[1:]:
        values = [
            value.strip()
            for value in re.split(r"\s{2,}|\t+", line.strip())
            if value.strip()
        ]
        if len(values) != len(fields):
            continue
        rows.append({
            field: _parse_value(value)
            for field, value in zip(fields, values)
        })
    return fields, tuple(rows)


def _sql_context(query: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if not query:
        return (), (), ()
    filters = []
    where = re.search(
        r"\bwhere\b(?P<body>.*?)(?=\bgroup\s+by\b|\border\s+by\b|\bhaving\b|$)",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if where:
        filters.append(" ".join(where.group("body").split()))
    group_by = []
    grouped = re.search(
        r"\bgroup\s+by\b(?P<body>.*?)(?=\border\s+by\b|\bhaving\b|$)",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if grouped:
        group_by = [
            value.strip()
            for value in grouped.group("body").split(",")
            if value.strip()
        ]
    aggregations = [
        match.group(1).upper()
        for match in re.finditer(
            r"\b(COUNT|COUNT_BIG|SUM|AVG|MIN|MAX)\s*\(",
            query,
            flags=re.IGNORECASE,
        )
    ]
    return (
        tuple(filters),
        tuple(group_by),
        tuple(dict.fromkeys(aggregations)),
    )


def _normalized_number(value: int | float) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{float(value):.12f}".rstrip("0").rstrip(".")


def build_evidence_frame(record: EvidenceRecord) -> EvidenceFrame:
    raw_lower = record.raw_result.casefold()
    query = _query_text(record)
    filters, group_by, aggregations = _sql_context(query)
    fields, parsed_rows = _tabular_rows(record.raw_result)
    is_error = any(marker in raw_lower for marker in ERROR_MARKERS)
    is_empty = any(marker in raw_lower for marker in EMPTY_MARKERS)
    schema_like = (
        "context" in record.tool_name.casefold()
        or "schema" in record.tool_name.casefold()
        or '"database_info"' in raw_lower
    )
    if is_error:
        result_kind = "error"
    elif is_empty:
        result_kind = "empty"
    elif schema_like:
        result_kind = "schema"
    elif parsed_rows:
        result_kind = "tabular"
    else:
        result_kind = "text"
    if schema_like:
        grain = "metadata"
    elif group_by:
        grain = "group"
    elif aggregations:
        grain = "aggregate"
    elif parsed_rows:
        grain = "record"
    else:
        grain = "unknown"

    labels = []
    numbers = []
    for row in parsed_rows:
        for value in row.values():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                numbers.append(_normalized_number(value))
            elif isinstance(value, str) and value:
                labels.append(value)
    return EvidenceFrame(
        evidence_id=record.evidence_id,
        tool_name=record.tool_name,
        action_succeeded=not is_error,
        result_kind=result_kind,
        fields=fields,
        rows=tuple(
            tuple(row.items()) for row in parsed_rows
        ),
        query=query,
        filters=filters,
        group_by=group_by,
        aggregations=aggregations,
        grain=grain,
        canonical_labels=tuple(dict.fromkeys(labels)),
        numeric_values=tuple(dict.fromkeys(numbers)),
        result_hash=record.result_hash,
    )


def _number_tokens(text: str) -> set[str]:
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    values = set()
    for match in re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?", text):
        normalized = match.replace(",", "")
        percent = normalized.endswith("%")
        core = normalized[:-1] if percent else normalized
        if "." in core:
            core = core.rstrip("0").rstrip(".")
        values.add(core + ("%" if percent else ""))
    return values


def _supported_number(token: str, allowed: set[str]) -> bool:
    if token in allowed:
        return True
    token_percent = token.endswith("%")
    try:
        value = float(token.rstrip("%"))
    except ValueError:
        return False
    for candidate in allowed:
        if candidate.endswith("%") != token_percent:
            continue
        try:
            expected = float(candidate.rstrip("%"))
        except ValueError:
            continue
        # Display rounding to two decimals is context-faithful.  This matches
        # the deterministic claim gate tolerance and still rejects materially
        # different or invented values.
        if math.isclose(value, expected, rel_tol=1e-4, abs_tol=0.011):
            return True
    return False


def _claim_is_present(answer: str, claim: str, labels: Iterable[str]) -> bool:
    numbers = _number_tokens(claim)
    claim_labels = {
        label for label in labels if label and label in claim
    }
    if numbers or claim_labels:
        return numbers.issubset(_number_tokens(answer)) and all(
            _canonical_label_present(answer, label)
            for label in claim_labels
        )
    normalized = " ".join(claim.casefold().split())
    return normalized in " ".join(answer.casefold().split())


def _canonical_label_present(text: str, label: str) -> bool:
    """Do not count a canonical label embedded in a normalized/relabelled word."""
    allowed_prefixes = ("แผนก", "ฝ่าย", "ประเภท", "หมวด", "สถานะ")
    for match in re.finditer(re.escape(label), text):
        start, end = match.span()
        before = text[:start]
        after = text[end:]
        if any(before.endswith(prefix) for prefix in allowed_prefixes):
            return True
        previous = before[-1:] if before else ""
        following = after[:1]
        previous_embedded = bool(re.fullmatch(r"[A-Za-z0-9_ก-๙]", previous))
        following_embedded = bool(re.fullmatch(r"[A-Za-z0-9_ก-๙]", following))
        if not previous_embedded and not following_embedded:
            return True
    return False


INFERENCE_MARKERS = (
    "indicates", "suggests", "implies", "therefore", "because",
    "แสดงว่า", "ชี้ว่า", "บ่งชี้ว่า", "หมายความว่า", "ทำให้",
    "ดังนั้น", "เนื่องจาก",
)


def _unsupported_interpretations(
    answer: str,
    required_claims: tuple[str, ...],
) -> tuple[str, ...]:
    """Find inference-bearing lines not present in a verified claim set."""
    verified = "\n".join(required_claims).casefold()
    unsupported = []
    for raw in answer.splitlines():
        line = re.sub(r"^\s*(?:[-*+]\s*|\d+[.)]\s*)", "", raw).strip()
        lowered = line.casefold()
        if not line or not any(marker in lowered for marker in INFERENCE_MARKERS):
            continue
        if line.casefold() in verified:
            continue
        unsupported.append(line)
    return tuple(dict.fromkeys(unsupported))


def reconcile_answer_with_context(
    question: str,
    answer: str,
    evidence: EvidenceState,
    *,
    required_claims: tuple[str, ...] = (),
) -> ContextFidelityReport:
    """Measure fidelity to accepted tool context without an LLM judge."""
    frames = tuple(
        frame for frame in evidence.frames
        if isinstance(frame, EvidenceFrame)
    )
    labels = tuple(dict.fromkeys(
        label for frame in frames for label in frame.canonical_labels
    ))
    allowed_numbers = _number_tokens(question)
    for record in evidence.records:
        allowed_numbers.update(_number_tokens(record.raw_result))
        allowed_numbers.update(_number_tokens(json.dumps(
            record.arguments, ensure_ascii=False, default=str
        )))
    # Contract-composed claims are deterministic derivations over accepted
    # evidence, so their numeric values are valid context too.
    for claim in required_claims:
        allowed_numbers.update(_number_tokens(claim))
    answer_numbers = _number_tokens(answer)
    unsupported_numbers = tuple(sorted(
        token for token in answer_numbers
        if not _supported_number(token, allowed_numbers)
    ))
    numeric_precision = (
        1.0
        if not answer_numbers
        else (len(answer_numbers) - len(unsupported_numbers))
        / len(answer_numbers)
    )

    required_labels = tuple(
        label for label in labels
        if any(label in claim for claim in required_claims)
    )
    missing_labels = tuple(
        label for label in required_labels
        if not _canonical_label_present(answer, label)
    )
    label_recall = (
        None
        if not required_labels
        else (len(required_labels) - len(missing_labels))
        / len(required_labels)
    )

    missing_claims = tuple(
        claim for claim in required_claims
        if not _claim_is_present(answer, claim, labels)
    )
    claim_recall = (
        None
        if not required_claims
        else (len(required_claims) - len(missing_claims))
        / len(required_claims)
    )
    unsupported_interpretations = _unsupported_interpretations(
        answer,
        required_claims,
    )
    successful = sum(frame.action_succeeded for frame in frames)
    if not evidence.records or not successful:
        status = "insufficient_evidence"
    elif unsupported_numbers:
        status = "contradicted"
    elif missing_claims or missing_labels or unsupported_interpretations:
        status = "partially_supported"
    else:
        status = "supported"
    return ContextFidelityReport(
        status=status,
        evidence_frames=len(frames),
        successful_frames=successful,
        numeric_precision=round(numeric_precision, 6),
        canonical_label_recall=(
            round(label_recall, 6) if label_recall is not None else None
        ),
        required_claim_recall=(
            round(claim_recall, 6) if claim_recall is not None else None
        ),
        unsupported_numbers=unsupported_numbers,
        unsupported_interpretations=unsupported_interpretations,
        missing_labels=missing_labels,
        missing_claims=missing_claims,
    )

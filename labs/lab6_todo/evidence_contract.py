"""Generic deterministic contracts applied before evidence admission."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from labs.lab6_todo.evidence_state import EvidenceRecord, EvidenceState


class ContractDecision(str, Enum):
    ACCEPT = "accept"
    QUERY_MORE = "query_more"
    REJECT = "reject"


@dataclass(frozen=True)
class ContractResult:
    decision: ContractDecision
    reason: str


@dataclass(frozen=True)
class MetricContractStatus:
    contract_id: str | None
    satisfied: bool
    missing_roles: tuple[str, ...] = ()


_CONTRACT_PATH = Path(__file__).with_name("executable_metric_contracts.json")
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_CONTRACT_GLOB = "skills/*/references/answer_contracts.json"
CONTRACT_UNSET = object()


def _plain_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def _contract_threshold(contract: dict) -> tuple[str, float] | None:
    """Read a fixed decision boundary from the executable contract."""
    threshold = contract.get("parameters", {}).get("threshold")
    if not isinstance(threshold, dict):
        return None
    operator = threshold.get("operator")
    value = threshold.get("value")
    if operator not in {"gt", "gte", "lt", "lte"}:
        return None
    if not isinstance(value, (int, float)):
        return None
    return str(operator), float(value)


def _threshold_passes(value: float, operator: str, threshold: float) -> bool:
    return {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
    }[operator]


def _operator_label(operator: str) -> str:
    return {
        "gt": "มากกว่า",
        "gte": "ไม่น้อยกว่า",
        "lt": "น้อยกว่า",
        "lte": "ไม่เกิน",
    }[operator]


def _contracts() -> tuple[dict, ...]:
    paths = (
        _CONTRACT_PATH,
        *sorted(_REPO_ROOT.glob(_SKILL_CONTRACT_GLOB)),
    )
    contracts = []
    identifiers = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for contract in payload["contracts"]:
            identifier = contract["id"]
            if identifier in identifiers:
                raise ValueError(f"duplicate answer contract id: {identifier}")
            identifiers.add(identifier)
            contracts.append(contract)
    return tuple(contracts)


def all_metric_contracts() -> tuple[dict, ...]:
    """Return the discovered generic + Skill contracts as read-only inputs."""
    return _contracts()


def metric_contract_by_id(identifier: str) -> dict | None:
    """Resolve a contract id without trusting user-provided routing markers."""
    return next(
        (item for item in _contracts() if item["id"] == identifier),
        None,
    )


def matching_metric_contracts(question: str) -> tuple[dict, ...]:
    """Return every literal match; callers decide how to handle ambiguity."""
    lowered = question.lower()
    matches = []
    for contract in _contracts():
        if not all(
            term.lower() in lowered
            for term in contract["question_terms_all"]
        ):
            continue
        if not any(
            term.lower() in lowered
            for term in contract["question_terms_any"]
        ):
            continue
        matches.append(contract)
    return tuple(matches)


def select_metric_contract(question: str) -> dict | None:
    """Legacy literal selector; hybrid routing uses unique matches only."""
    matches = matching_metric_contracts(question)
    return matches[0] if matches else None


def _resolved_contract(question: str, contract):
    if contract is CONTRACT_UNSET:
        return select_metric_contract(question)
    return contract


def terminal_contract_verdict(
    question: str,
    *,
    contract=CONTRACT_UNSET,
) -> str | None:
    contract = _resolved_contract(question, contract)
    if not contract:
        return None
    verdict = contract.get("terminal_verdict")
    return str(verdict) if verdict else None


def _query_text(record: EvidenceRecord) -> str:
    for key in ("query", "sql", "statement"):
        value = record.arguments.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(record.arguments, ensure_ascii=False, default=str)


def _matching_role(contract: dict, query: str) -> dict | None:
    lowered = f" {query.lower()} "
    for role in contract["roles"]:
        if any(term.lower() in lowered for term in role["table_terms"]):
            return role
    return None


def _role_query_valid(role: dict, query: str) -> tuple[bool, str]:
    lowered = f" {query.lower()} "
    missing = [
        term for term in role["query_terms_all"]
        if term.lower() not in lowered
    ]
    forbidden = [
        term for term in role["query_terms_forbidden"]
        if term.lower() in lowered
    ]
    if missing:
        return False, "missing query contract terms: " + ", ".join(missing)
    if forbidden:
        return False, "forbidden query contract terms: " + ", ".join(forbidden)
    return True, "query role contract passed"


def _role_result_valid(role: dict, raw_result: str) -> bool:
    lowered = raw_result.lower()
    lines = [line for line in raw_result.splitlines() if line.strip()]
    fields_ok = not role["result_fields_any"] or any(
        field.lower() in lowered for field in role["result_fields_any"]
    )
    required_ok = all(
        term.lower() in lowered
        for term in role["result_must_contain"]
    )
    return (
        fields_ok
        and required_ok
        and len(lines) >= role["minimum_result_lines"]
    )


def repair_query_arguments(
    question: str,
    tool_name: str,
    arguments: dict,
    *,
    contract=CONTRACT_UNSET,
) -> tuple[dict, tuple[str, ...]]:
    """Apply only contract-declared, semantics-preserving query repairs."""
    if "query" not in tool_name.lower():
        return arguments, ()
    key = next(
        (item for item in ("query", "sql", "statement")
         if isinstance(arguments.get(item), str)),
        None,
    )
    if not key:
        return arguments, ()
    query = arguments[key]
    repairs = []

    def unicode_replacement(match: re.Match) -> str:
        prefix = match.group("prefix")
        value = match.group("value")
        if any(ord(char) > 127 for char in value) and not prefix:
            repairs.append("mssql-unicode-prefix")
            return "N'" + value + "'"
        return match.group(0)

    query = re.sub(
        r"(?P<prefix>[Nn]?)'(?P<value>(?:''|[^'])*)'",
        unicode_replacement,
        query,
    )
    contract = _resolved_contract(question, contract)
    if contract and contract["id"] == "performance_review_coverage":
        lowered = query.lower()
        if "performance_review" in lowered and "distinct" not in lowered:
            repaired = re.sub(
                r"count\s*\(\s*\*\s*\)",
                "COUNT(DISTINCT employee_id)",
                query,
                count=1,
                flags=re.IGNORECASE,
            )
            if repaired != query:
                query = repaired
                repairs.append("coverage-distinct-employee")
    if not repairs:
        return arguments, ()
    updated = dict(arguments)
    updated[key] = query
    return updated, tuple(dict.fromkeys(repairs))


def _has_unsafe_unicode_literal(query: str) -> bool:
    """MSSQL requires N'…' for Unicode string literals."""
    for match in re.finditer(r"(?P<prefix>[Nn]?)'(?P<value>(?:''|[^'])*)'", query):
        value = match.group("value")
        if any(ord(char) > 127 for char in value):
            if match.group("prefix").lower() != "n":
                return True
    return False


def validate_evidence_contract(
    question: str,
    record: EvidenceRecord,
    *,
    contract=CONTRACT_UNSET,
) -> ContractResult:
    if "query" not in record.tool_name.lower():
        return ContractResult(ContractDecision.ACCEPT, "non-query evidence")
    query = _query_text(record)
    if _has_unsafe_unicode_literal(query):
        return ContractResult(
            ContractDecision.REJECT,
            "MSSQL Unicode filter literal must use N'…'",
        )
    lowered_question = question.lower()
    lowered_query = query.lower()
    if (
        any(term in lowered_question for term in ("coverage", "ความครอบคลุม"))
        and "performance_review" in lowered_query
        and "count(" in lowered_query
        and "distinct" not in lowered_query
    ):
        return ContractResult(
            ContractDecision.QUERY_MORE,
            "coverage numerator requires distinct entity grain",
        )
    metric_contract = _resolved_contract(question, contract)
    if metric_contract:
        role = _matching_role(metric_contract, query)
        if role:
            valid, reason = _role_query_valid(role, query)
            if not valid:
                return ContractResult(ContractDecision.QUERY_MORE, reason)
            if not _role_result_valid(role, record.raw_result):
                return ContractResult(
                    ContractDecision.QUERY_MORE,
                    f"result does not satisfy role {role['id']}",
                )
    return ContractResult(ContractDecision.ACCEPT, "contract checks passed")


def metric_contract_status(
    question: str,
    evidence: EvidenceState,
    *,
    contract=CONTRACT_UNSET,
) -> MetricContractStatus:
    contract = _resolved_contract(question, contract)
    if not contract:
        return MetricContractStatus(None, True)
    satisfied_roles = set()
    for record in evidence.records:
        query = _query_text(record)
        role = _matching_role(contract, query)
        if not role:
            continue
        valid, _ = _role_query_valid(role, query)
        if valid and _role_result_valid(role, record.raw_result):
            satisfied_roles.add(role["id"])
    required = {role["id"] for role in contract["roles"]}
    missing = tuple(sorted(required - satisfied_roles))
    return MetricContractStatus(
        contract["id"],
        not missing,
        missing,
    )


def missing_role_queries(
    question: str,
    evidence: EvidenceState,
    *,
    contract=CONTRACT_UNSET,
) -> tuple[tuple[str, str], ...]:
    contract = _resolved_contract(question, contract)
    status = metric_contract_status(
        question,
        evidence,
        contract=contract,
    )
    if not contract or status.satisfied:
        return ()
    by_id = {role["id"]: role for role in contract["roles"]}
    return tuple(
        (role_id, by_id[role_id]["query_template"])
        for role_id in status.missing_roles
    )


def contract_claims(
    question: str,
    evidence: EvidenceState,
    *,
    contract=CONTRACT_UNSET,
) -> tuple[str, ...]:
    contract = _resolved_contract(question, contract)
    status = metric_contract_status(
        question,
        evidence,
        contract=contract,
    )
    if not status.satisfied or not status.contract_id:
        return ()
    assert contract is not None
    role_records: dict[str, EvidenceRecord] = {}
    for record in evidence.records:
        role = _matching_role(contract, _query_text(record))
        if role:
            valid, _ = _role_query_valid(role, _query_text(record))
            if valid and _role_result_valid(role, record.raw_result):
                role_records[role["id"]] = record
    output = contract.get("output")
    if output:
        role_id = output["role_id"]
        record = role_records.get(role_id)
        if not record:
            return ()
        required_columns = tuple(output["required_columns"])
        rows = _parse_result_rows(
            record.raw_result,
            required_columns,
            output.get("spaced_column"),
        )
        if not rows or any(
            any(column not in row for column in required_columns)
            for row in rows
        ):
            return ()
        claims = []
        suffixes = {
            str(column): str(suffix)
            for column, suffix in output.get("suffixes", {}).items()
        }
        for row in rows:
            claims.append("; ".join(
                f"{column}={row[column]}{suffixes.get(column, '')}"
                for column in required_columns
            ))
        claims.extend(map(str, output.get("grounded_notes", ())))
        return tuple(claims)
    if status.contract_id == "active_headcount_by_department":
        record = role_records["grouped_active_headcount"]
        rows = []
        for line in record.raw_result.splitlines()[1:]:
            match = re.match(r"\s*(.+?)\s{2,}(\d+)\s*$", line)
            if match:
                rows.append((match.group(1).strip(), int(match.group(2))))
        if not rows:
            return ()
        total = sum(count for _, count in rows)
        return (
            f"พนักงานที่มีสถานะ `ปฏิบัติงาน` มีทั้งหมด {total} คน",
            *(f"แผนก{label} มีพนักงาน {count} คน" for label, count in rows),
        )
    if status.contract_id == "performance_review_coverage":
        def scalar(role_id: str) -> int | None:
            values = re.findall(r"(?<![\w.])\d+(?![\w.])", role_records[role_id].raw_result)
            return int(values[-1]) if values else None
        total = scalar("active_employee_denominator")
        reviewed = scalar("distinct_reviewed_employee_numerator")
        threshold_spec = _contract_threshold(contract)
        review_period = contract.get("parameters", {}).get("review_period")
        if (
            total is None
            or reviewed is None
            or threshold_spec is None
            or not review_period
            or total <= 0
        ):
            return ()
        operator, threshold = threshold_spec
        coverage = reviewed / total * 100
        verdict = (
            "ผ่าน"
            if _threshold_passes(coverage, operator, threshold)
            else "ไม่ผ่าน"
        )
        return (
            f"พนักงานที่ปฏิบัติงานทั้งหมดคือ {total} คน",
            (
                "พนักงานที่มี performance review ปี "
                f"{review_period} คือ {reviewed} คน"
            ),
            f"Evidence coverage ของพนักงานที่มี review เท่ากับ {reviewed} / {total} = {coverage:g}%",
            f"{verdict}เกณฑ์ขั้นต่ำ {threshold:g}%",
        )
    if status.contract_id == "training_certificate_semantic_separation":
        values = [
            int(item)
            for item in re.findall(
                r"(?<![\w.])\d+(?![\w.])",
                role_records["training_certificate_flags"].raw_result,
            )
        ]
        if len(values) < 2:
            return ()
        total, obtained = values[-2:]
        claims = [
            f"training records มีทั้งหมด {total} รายการ",
            (
                f"ทุกรายการอบรมทั้ง {total} รายการมี "
                "`certificate_obtained = True`"
                if total == obtained
                else (
                    f"training records ที่มี `certificate_obtained = True` "
                    f"มี {obtained} จาก {total} รายการ"
                )
            ),
            (
                "`certificate_obtained` เป็นหลักฐานที่ grain ของ "
                "training record ไม่ใช่หลักฐานว่า employee ทุกคนมี "
                "certification ที่ยังใช้ได้"
            ),
        ]
        return tuple(claims)
    if status.contract_id == "training_hours_portfolio":
        record = role_records["hours_by_training_type"]
        rows = []
        for line in record.raw_result.splitlines()[1:]:
            columns = re.split(r"\s{2,}", line.strip(), maxsplit=1)
            if len(columns) != 2:
                continue
            first_value = re.search(
                r"-?\d[\d,]*(?:\.\d+)?",
                columns[1],
            )
            if first_value:
                rows.append((
                    columns[0],
                    float(first_value.group(0).replace(",", "")),
                ))
        total = sum(value for _, value in rows)
        threshold_spec = _contract_threshold(contract)
        if not rows or total <= 0 or threshold_spec is None:
            return ()
        operator, threshold = threshold_spec
        claims = [f"ชั่วโมงอบรมทั้งหมดคือ {total:g} ชั่วโมง"]
        for label, value in rows:
            share = value / total * 100
            passed = _threshold_passes(share, operator, threshold)
            verdict = (
                "เกิน" if passed and operator == "gt"
                else "ไม่เกิน" if operator == "gt"
                else "ผ่าน" if passed
                else "ไม่ผ่าน"
            )
            claims.append(
                f"{label} {value:g} ชั่วโมง ({share:.2f}%) "
                f"{verdict}นโยบาย concentration limit "
                f"{_operator_label(operator)} {threshold:g}%"
            )
        return tuple(claims)
    if status.contract_id == "staffing_decision_insufficient":
        record = role_records["descriptive_active_headcount"]
        rows = []
        for line in record.raw_result.splitlines()[1:]:
            match = re.match(r"\s*(.+?)\s{2,}(\d+)\s*$", line)
            if match:
                rows.append((match.group(1).strip(), int(match.group(2))))
        return tuple(
            f"แผนก{label} มีพนักงานปฏิบัติงาน {count} คน"
            for label, count in rows
        )
    if status.contract_id == "project_value_per_active_employee":
        record = role_records["department_value_and_headcount"]
        requested_labels = set(re.findall(r"`([^`]+)`", question))
        claims = []
        for line in record.raw_result.splitlines()[1:]:
            match = re.match(
                r"\s*(.+?)\s{2,}(\d+)\s+"
                r"(-?\d[\d,]*(?:\.\d+)?)\s*$",
                line,
            )
            if not match:
                continue
            label = match.group(1).strip()
            if requested_labels and label not in requested_labels:
                continue
            count = int(match.group(2))
            value = float(match.group(3).replace(",", ""))
            if count <= 0:
                continue
            claims.append(
                f"project value ต่อพนักงานของ {label} = "
                f"{value:g} / {count} = {value / count:.2f}"
            )
        return tuple(claims)
    if status.contract_id == "expert_skill_record_share":
        record = role_records["expert_share_by_category"]
        rows = []
        for line in record.raw_result.splitlines()[1:]:
            match = re.match(
                r"\s*(.+?)\s{2,}(\d+)\s+(\d+)\s*$",
                line,
            )
            if match:
                rows.append((
                    match.group(1).strip(),
                    int(match.group(2)),
                    int(match.group(3)),
                ))
        threshold_spec = _contract_threshold(contract)
        if not rows or threshold_spec is None:
            return ()
        operator, threshold = threshold_spec
        claims = []
        for label, total, expert in rows:
            if total <= 0:
                continue
            share = expert / total * 100
            verdict = (
                "ผ่าน"
                if _threshold_passes(share, operator, threshold)
                else "ไม่ผ่าน"
            )
            claims.append(
                f"{label} มี skill records {total} รายการ "
                f"และระดับเชี่ยวชาญ {expert} รายการ "
                f"คิดเป็น {share:.2f}% ซึ่ง{verdict}เกณฑ์ "
                f"{_operator_label(operator)} {threshold:g}%"
            )
        return tuple(claims)
    if status.contract_id == "top_two_project_concentration":
        record = role_records["portfolio_total_and_top_two"]
        values = [
            float(item.replace(",", ""))
            for item in re.findall(
                r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?![\w.])",
                record.raw_result,
            )
        ]
        threshold_spec = _contract_threshold(contract)
        if len(values) < 2 or threshold_spec is None or values[-2] <= 0:
            return ()
        total, top_two = values[-2:]
        operator, threshold = threshold_spec
        share = top_two / total * 100
        verdict = (
            "มี concentration risk"
            if _threshold_passes(share, operator, threshold)
            else "ไม่มี concentration risk ตามเกณฑ์"
        )
        return (
            f"มูลค่าโครงการรวมทั้งหมดคือ {_plain_number(total)}",
            (
                "มูลค่าโครงการสูงสุดสองอันดับรวมคือ "
                f"{_plain_number(top_two)}"
            ),
            f"สัดส่วน top two ต่อทั้งหมดคือ {share:.2f}%",
            (
                "เกณฑ์นโยบายคือ "
                f"{_operator_label(operator)} {threshold:g}%"
            ),
            verdict,
        )
    return ()


def _parse_result_rows(
    raw_result: str,
    columns: tuple[str, ...],
    spaced_column: str | None = None,
) -> tuple[dict[str, str], ...]:
    """Parse MCP tabular text under a contract-declared column shape."""
    lines = [line.rstrip() for line in raw_result.splitlines() if line.strip()]
    if len(lines) < 2:
        return ()
    headers = tuple(re.findall(r"\S+", lines[0]))
    if not headers or set(headers) != set(columns):
        return ()
    spaced_index = (
        columns.index(spaced_column)
        if spaced_column in columns
        else None
    )
    rows = []
    for line in lines[1:]:
        tokens = line.split()
        if spaced_index is None:
            values = tokens
        else:
            spaced_width = len(tokens) - len(columns) + 1
            if spaced_width < 1:
                continue
            values = (
                tokens[:spaced_index]
                + [" ".join(tokens[
                    spaced_index:spaced_index + spaced_width
                ])]
                + tokens[spaced_index + spaced_width:]
            )
        if len(values) != len(columns) or any(not value for value in values):
            continue
        by_header = dict(zip(headers, values))
        rows.append({column: by_header[column] for column in columns})
    return tuple(rows)

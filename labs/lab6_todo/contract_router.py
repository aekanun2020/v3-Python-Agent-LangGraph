"""Hybrid contract routing: lexical fast path, semantic proposal, hard gate."""
from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Callable

from labs.core import config, llm
from labs.lab6_todo.evidence_contract import (
    all_metric_contracts,
    matching_metric_contracts,
    metric_contract_by_id,
)
from labs.lab6_todo.phase2_runtime import RuntimeBudgetExhausted
from labs.lab6_todo.intent_frame import (
    ComparisonBinding,
    NumericRole,
    analyze_intent_frame,
)


class RoutingPath(str, Enum):
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class RoutingDecision:
    contract_id: str | None
    path: RoutingPath
    confidence: float
    reason: str
    term_evidence: tuple[tuple[str, str], ...] = ()
    semantic_attempted: bool = False
    parameter_bindings: tuple[ComparisonBinding, ...] = ()

    @property
    def contract(self) -> dict | None:
        if not self.contract_id:
            return None
        contract = metric_contract_by_id(self.contract_id)
        if contract is None or not self.parameter_bindings:
            return contract
        bound = deepcopy(contract)
        for binding in self.parameter_bindings:
            bound.setdefault("parameters", {})[binding.parameter] = {
                "operator": binding.operator,
                "value": binding.value,
                "unit": binding.unit,
            }
        return bound


SemanticResolver = Callable[[str, tuple[dict, ...]], dict]


_ROOT = Path(__file__).resolve().parents[2]
_ROUTING_GLOB = "skills/*/references/routing_catalog.json"
_MIN_CONFIDENCE = 0.80
_MAX_OUTPUT_TOKENS = 1600
_PROMPT_VERSION = "hybrid-contract-router-v3"
# Bump whenever deterministic admission logic changes. Evaluation artifacts
# must identify both the model-facing prompt/catalog and the Python hard gate.
_GATE_VERSION = "skill-grounded-admission-gate-v2"


def _validate_constraint_bindings(answer: dict) -> None:
    """Prevent routing constants from drifting from answer parameters."""
    parameters = answer.get("parameters", {})
    bound_parameters = set()
    for constraint in answer.get("routing_constraints", ()):
        parameter_name = constraint.get("parameter")
        if not isinstance(parameter_name, str) or parameter_name not in parameters:
            raise ValueError(
                f"routing constraint {constraint.get('name')} has no "
                f"bound answer parameter in {answer['id']}"
            )
        bound_parameters.add(parameter_name)
        bound = parameters[parameter_name]
        kind = constraint.get("kind")
        if kind == "comparison":
            expected = {
                key: constraint.get(key)
                for key in ("operator", "value", "unit")
            }
            actual = {
                key: bound.get(key) if isinstance(bound, dict) else None
                for key in ("operator", "value", "unit")
            }
        elif kind == "closed_range":
            expected = {
                key: constraint.get(key) for key in ("start", "end")
            }
            actual = {
                key: bound.get(key) if isinstance(bound, dict) else None
                for key in ("start", "end")
            }
        elif kind == "ordered_boundaries":
            expected = constraint.get("values")
            actual = bound
        elif kind == "fixed_value":
            expected = constraint.get("value")
            actual = bound
        else:
            raise ValueError(
                f"unsupported routing constraint kind in {answer['id']}: "
                f"{kind}"
            )
        if actual != expected:
            raise ValueError(
                f"routing/answer parameter drift in {answer['id']}: "
                f"{parameter_name}"
            )
    unbound = sorted(set(parameters) - bound_parameters)
    if unbound:
        raise ValueError(
            f"query-affecting parameters lack routing constraints in "
            f"{answer['id']}: " + ", ".join(unbound)
        )


def _routing_catalog() -> tuple[dict, ...]:
    answer_contracts = {
        item["id"]: item for item in all_metric_contracts()
    }
    entries = []
    identifiers = set()
    for path in sorted(_ROOT.glob(_ROUTING_GLOB)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["contracts"]:
            identifier = item["id"]
            if identifier in identifiers:
                raise ValueError(f"duplicate routing contract id: {identifier}")
            if identifier not in answer_contracts:
                raise ValueError(
                    f"routing contract has no answer contract: {identifier}"
                )
            identifiers.add(identifier)
            answer = answer_contracts[identifier]
            _validate_constraint_bindings(answer)
            routing_all = item.get(
                "required_concepts",
                answer["question_terms_all"],
            )
            routing_any = item.get(
                "one_of_concepts",
                answer["question_terms_any"],
            )
            declared_patterns = item.get("concept_evidence_patterns", {})
            concept_patterns = {
                concept: declared_patterns.get(
                    concept,
                    [re.escape(str(concept))],
                )
                for concept in (*routing_all, *routing_any)
            }
            entries.append({
                **item,
                "question_terms_all": answer["question_terms_all"],
                "question_terms_any": answer["question_terms_any"],
                "routing_concepts_all": routing_all,
                "routing_concepts_any": routing_any,
                "concept_evidence_patterns": concept_patterns,
                "terminal_verdict": answer.get("terminal_verdict"),
                # Fixed business values live with the executable answer
                # contract. The model may propose a contract, but only this
                # deterministic gate may admit its thresholds/ranges.
                "routing_constraints": answer.get(
                    "routing_constraints",
                    (),
                ),
            })
    missing = sorted(set(answer_contracts) - identifiers)
    if missing:
        raise ValueError(
            "answer contracts missing routing catalog entries: "
            + ", ".join(missing)
        )
    return tuple(entries)


def router_fingerprint() -> dict:
    """Version routing inputs without treating model output as evidence."""
    catalog = _routing_catalog()
    effective_catalog = []
    for item in catalog:
        normalized = dict(item)
        normalized["routing_constraints"] = [
            {
                key: value
                for key, value in constraint.items()
                if key != "parameter"
            }
            for constraint in item.get("routing_constraints", ())
        ]
        effective_catalog.append(normalized)
    encoded = json.dumps(
        effective_catalog,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return {
        "prompt_version": _PROMPT_VERSION,
        "gate_version": _GATE_VERSION,
        "gate_source_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "model": config.ROUTER_MODEL,
        "request_timeout_seconds": config.ROUTER_TIMEOUT_SECONDS,
        "max_output_tokens": _MAX_OUTPUT_TOKENS,
        "reasoning_effort": "low",
        "minimum_confidence": _MIN_CONFIDENCE,
    }


def _semantic_prompt(question: str, catalog: tuple[dict, ...]) -> list[dict]:
    compact_catalog = [{
        "id": item["id"],
        "intent": item["intent"],
        "exclude": item["exclude"],
        # These strings name business concepts inherited from the executable
        # contract. They are not literal-substring requirements.
        "required_concepts": item["routing_concepts_all"],
        "one_of_concepts": item["routing_concepts_any"],
        "fixed_constraints": [
            {
                key: value
                for key, value in constraint.items()
                if key not in {
                    "evidence_pattern_groups",
                    "conflict_pattern_groups",
                    "allowed_auxiliary_numbers",
                    "reject_unlisted_numbers",
                    "parameter",
                }
            }
            for constraint in item.get("routing_constraints", ())
        ],
        "verdict": item.get("terminal_verdict"),
    } for item in catalog]
    return [
        {
            "role": "system",
            "content": (
                "You are a conservative intent extractor, not an answerer. "
                "Choose one contract only when its business operation, metric, "
                "population, grain, filters, thresholds, and decision scope all "
                "match. fixed_constraints are mandatory exact business values, "
                "not suggestions. Otherwise abstain. A refuse_decision contract is a valid "
                "match when the user asks for that prohibited/unsupported "
                "decision. Return JSON only with keys contract_id, confidence, "
                "reason, term_evidence. contract_id must be a listed id or null. "
                "The concept labels are meanings, NOT words that must literally "
                "occur. Match Thai/English paraphrases. term_evidence must map "
                "every required_concepts item and, when one_of_concepts is not "
                "empty, at least one of those items to an exact non-empty quote "
                "copied from the user question. "
                "Each quote must express the mapped concept; do not reuse one "
                "generic quote for unrelated concepts. Never invent text not "
                "present in the question. When abstaining use an empty object "
                "for term_evidence."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({
                "question": question,
                "contracts": compact_catalog,
            }, ensure_ascii=False),
        },
    ]


def _parse_json_object(content: str) -> dict:
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        # Some providers wrap valid JSON in reasoning or markdown. Decode the
        # first complete object instead of greedily merging multiple braces.
        decoder = json.JSONDecoder()
        value = None
        for match in re.finditer(r"\{", content):
            try:
                candidate, _end = decoder.raw_decode(content[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                value = candidate
                break
        if value is None:
            raise ValueError("semantic router did not return a JSON object")
    if not isinstance(value, dict):
        raise ValueError("semantic router output must be an object")
    return value


def openrouter_semantic_resolver(
    question: str,
    catalog: tuple[dict, ...],
) -> dict:
    """Ask one model for a grounded candidate; never execute its decision."""
    identifiers = [item["id"] for item in catalog]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "contract_route",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "contract_id": {
                        "anyOf": [
                            {"type": "string", "enum": identifiers},
                            {"type": "null"},
                        ]
                    },
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                    "term_evidence": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": [
                    "contract_id",
                    "confidence",
                    "reason",
                    "term_evidence",
                ],
                "additionalProperties": False,
            },
        },
    }
    response = llm.chat(
        messages=_semantic_prompt(question, catalog),
        model=config.ROUTER_MODEL,
        temperature=0,
        max_tokens=_MAX_OUTPUT_TOKENS,
        response_format=response_format,
        reasoning_effort="low",
        timeout=config.ROUTER_TIMEOUT_SECONDS,
        # A timeout is an abstention, not a reason to make the user wait for a
        # second non-deterministic routing proposal.
        client_max_retries=0,
    )
    return _parse_json_object(response.choices[0].message.content or "")


def _quote_is_grounded(question: str, quote: object) -> bool:
    if not isinstance(quote, str) or not quote.strip():
        return False
    return quote.strip().casefold() in question.casefold()


def _quote_expresses_concept(entry: dict, concept: str, quote: str) -> bool:
    patterns = entry.get("concept_evidence_patterns", {}).get(concept, ())
    if not patterns or not all(isinstance(pattern, str) for pattern in patterns):
        return False
    try:
        return any(
            re.search(pattern, quote, flags=re.IGNORECASE)
            for pattern in patterns
        )
    except re.error:
        return False


def _critical_anchors_hold(question: str, entry: dict) -> bool:
    required_groups = entry.get("critical_anchor_groups", [])
    required_hold = all(
        any(
            _pattern_has_positive_match(re.escape(str(anchor)), question)
            for anchor in group
        )
        for group in required_groups
    )
    required_conflict = any(
        _pattern_has_negated_match(re.escape(str(anchor)), question)
        for group in required_groups
        for anchor in group
    )
    forbidden_hit = any(
        _pattern_has_positive_match(re.escape(str(anchor)), question)
        for anchor in entry.get("forbidden_anchors", [])
    )
    return required_hold and not required_conflict and not forbidden_hit


_NEGATED_OPERATION = re.compile(
    r"(?:^|[.!?\n]\s*)"
    r"(?:ไม่ต้องการ|ไม่ต้อง|อย่า(?!ง)|do\s+not|don't)\s*"
    r"(?:ให้\s*)?"
    r"(?:สรุป|นับ|แจกแจง|เปรียบเทียบ|คำนวณ|คัด|หา|แสดง|วัด|ตรวจ|รายงาน|แบ่ง|"
    r"summari[sz]e|count|list|compare|calculate|show|report|bucket)",
    flags=re.IGNORECASE,
)
_LEADING_NEGATIVE_REQUEST = re.compile(
    r"^\s*(?:ไม่ต้องการ|ไม่ต้อง|อย่า(?!ง)|do\s+not|don't)",
    flags=re.IGNORECASE,
)
_SCHEMA_ONLY = re.compile(
    r"(?:"
    r"(?:แค่|เพียง|เท่านั้น|อย่างเดียว|อธิบาย|ขอ|only|just)"
    r"[^\n.!?]{0,40}(?:schema|โครงสร้างตาราง)"
    r"|(?:schema|โครงสร้างตาราง)[^\n.!?]{0,30}"
    r"(?:เท่านั้น|อย่างเดียว|only)"
    r")",
    flags=re.IGNORECASE,
)
_EXPLICIT_OVERRIDE = re.compile(
    r"(?:"
    r"เดิม[^\n.!?]{0,80}(?:แต่|แต่ขอ|แต่ให้)[^\n.!?]{0,24}"
    r"(?:ใช้|เปลี่ยนเป็น)"
    r"|เปลี่ยนเป็น[^\n.!?]{1,40}แทน"
    r"|ใช้[^\n.!?]{1,40}แทน(?:ค่า|เกณฑ์|แบบ)?เดิม"
    r"|\b(?:instead\s+of|rather\s+than|replace[^\n.!?]{1,40}\bwith)\b"
    r")",
    flags=re.IGNORECASE,
)


def _request_boundary_holds(question: str) -> tuple[bool, str]:
    """Reject explicit non-requests before either routing path can run."""
    if _SCHEMA_ONLY.search(question):
        return False, "question requests schema only, not contract execution"
    if _NEGATED_OPERATION.search(question):
        return False, "contract operation is explicitly negated"
    # A negative-only imperative such as "ไม่ต้องการค่าเฉลี่ย ..." has no
    # positive operation to execute. Mid-sentence safety boundaries such as
    # "แต่อย่าตีความเป็นผลิตภาพ" do not match this prefix.
    if _LEADING_NEGATIVE_REQUEST.search(question):
        return False, "question is a negative-only request"
    if _EXPLICIT_OVERRIDE.search(question):
        return False, "question contains an explicit contract-value override"
    return True, "request boundary passed"


_TERM_NEGATION = re.compile(
    r"(?:ไม่(?:ต้องการ|ต้อง|รวม|เอา|ให้|ประสงค์)|อย่า(?!ง)|ยกเว้น|เว้น|ตัดออก|"
    r"exclude|without|omit(?:ted)?|ignore|skip|except|do\s+not|don't)"
    r"[^\n.!?]{0,24}$",
    flags=re.IGNORECASE,
)


def _contract_terms_hold(question: str, entry: dict) -> tuple[bool, str]:
    """Reject a matched contract term when the user explicitly negates it."""
    allowed = {
        str(term).casefold()
        for term in entry.get("allowed_negated_terms", ())
    }
    for rule in entry.get("conditional_allowed_negated_terms", ()):
        groups = rule.get("required_pattern_groups", ())
        try:
            holds = bool(groups) and all(
                any(
                    _pattern_has_positive_match(pattern, question)
                    for pattern in group
                )
                for group in groups
            )
        except (re.error, TypeError):
            holds = False
        if holds:
            allowed.add(str(rule.get("term", "")).casefold())
    terms = dict.fromkeys((
        *entry.get("question_terms_all", ()),
        *entry.get("question_terms_any", ()),
    ))
    for term in terms:
        normalized = str(term).casefold()
        if not normalized or normalized in allowed:
            continue
        for match in re.finditer(
            re.escape(str(term)),
            question,
            flags=re.IGNORECASE,
        ):
            if _span_is_negated(question, match.start(), match.end()):
                return False, f"contract term is explicitly negated: {term}"
    return True, "contract terms are not negated"


_POSTFIX_TERM_NEGATION = re.compile(
    r"^\s*(?:ไม่(?:ใช้|เอา|รวม|ต้องการ|ต้อง)|ยกเว้น|เว้น|ตัดออก|"
    r"exclude(?:d)?|without|omit(?:ted)?|ignore|skip|except|do\s+not\s+use)",
    flags=re.IGNORECASE,
)
_SPAN_LEADING_NEGATION = re.compile(
    r"^\s*(?:ไม่(?:ต้องการ|ต้อง|รวม|เอา|ให้|ใช้|ประสงค์)|อย่า(?!ง)|ยกเว้น|เว้น|ตัดออก|"
    r"exclude|without|omit(?:ted)?|ignore|skip|except|do\s+not|don't)",
    flags=re.IGNORECASE,
)


def _span_is_negated(question: str, start: int, end: int) -> bool:
    prefix = question[max(0, start - 48):start]
    if _TERM_NEGATION.search(prefix):
        return True
    if _SPAN_LEADING_NEGATION.match(question[start:end]):
        return True
    return bool(_POSTFIX_TERM_NEGATION.match(question[end:end + 48]))


def _pattern_has_positive_match(pattern: str, question: str) -> bool:
    return any(
        not _span_is_negated(question, match.start(), match.end())
        for match in re.finditer(pattern, question, flags=re.IGNORECASE)
    )


def _pattern_has_negated_match(pattern: str, question: str) -> bool:
    return any(
        _span_is_negated(question, match.start(), match.end())
        for match in re.finditer(pattern, question, flags=re.IGNORECASE)
    )


def _quote_is_negated(question: str, quote: str) -> bool:
    pattern = re.escape(quote.strip())
    matches = tuple(re.finditer(pattern, question, flags=re.IGNORECASE))
    return bool(matches) and all(
        _span_is_negated(question, match.start(), match.end())
        for match in matches
    )


def _numbers_in_question(question: str) -> set[float]:
    values = set()
    for raw in re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", question):
        try:
            values.add(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


_COMPARISON_OPERATOR_PATTERNS = {
    "gt": (
        r">(?!=)|(?<!ไม่)มากกว่า|(?<!ไม่)เกิน|(?<!ไม่)สูงกว่า|"
        r"\b(?:greater|more|higher)\s+than\b"
    ),
    "gte": (
        r">=|=>|ไม่น้อยกว่า|ไม่ต่ำกว่า|อย่างน้อย|ตั้งแต่|"
        r"\b(?:at\s+least|greater\s+than\s+or\s+equal(?:\s+to)?)\b"
    ),
    "lt": (
        r"<(?!=)|(?<!ไม่)น้อยกว่า|(?<!ไม่)ต่ำกว่า|"
        r"\b(?:less|lower)\s+than\b"
    ),
    "lte": (
        r"<=|=<|ไม่เกิน|ไม่มากกว่า|ไม่สูงกว่า|อย่างมาก|"
        r"\b(?:at\s+most|less\s+than\s+or\s+equal(?:\s+to)?)\b"
    ),
    "eq": r"==|(?<![<>])=(?!=)|เท่ากับ|เท่ากัน|\bequal(?:\s+to)?\b",
}


def _comparison_operator_conflict(
    question: str,
    expected_operator: str,
    value: object,
) -> bool:
    """Reject an explicit alternative operator around the fixed threshold."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    number = re.escape(f"{float(value):g}")
    unit = r"\s*(?:%|เปอร์เซ็นต์)?"
    for operator, operator_pattern in _COMPARISON_OPERATOR_PATTERNS.items():
        if operator == expected_operator:
            continue
        prefix = rf"(?:{operator_pattern})\s*{number}{unit}"
        suffix = rf"{number}{unit}\s*(?:{operator_pattern})"
        if re.search(prefix, question, flags=re.IGNORECASE):
            return True
        if re.search(suffix, question, flags=re.IGNORECASE):
            return True
    return False


def _bind_routing_constraints(
    question: str,
    entry: dict,
) -> tuple[bool, str, tuple[ComparisonBinding, ...]]:
    """Validate contract constants and bind grounded comparison parameters."""
    constraints = tuple(entry.get("routing_constraints", ()))
    frame = analyze_intent_frame(question)
    allowed_numbers: set[float] = set()
    reject_unlisted_numbers = False
    bindings: list[ComparisonBinding] = []

    def add_number(value: object) -> None:
        if isinstance(value, bool) or value is None:
            return
        try:
            allowed_numbers.add(float(value))
        except (TypeError, ValueError):
            return

    for constraint in constraints:
        reject_unlisted_numbers = (
            reject_unlisted_numbers
            or bool(constraint.get("reject_unlisted_numbers"))
        )
        kind = constraint.get("kind")
        if kind == "comparison":
            add_number(constraint.get("value"))
        elif kind == "closed_range":
            add_number(constraint.get("start"))
            add_number(constraint.get("end"))
        elif kind == "ordered_boundaries":
            for value in constraint.get("values", ()):
                add_number(value)
        elif kind == "fixed_value":
            add_number(constraint.get("value"))
        for value in constraint.get("allowed_auxiliary_numbers", ()):
            add_number(value)

    if reject_unlisted_numbers:
        guarded_numbers = {
            mention.value
            for mention in frame.numeric_mentions
            if mention.role is not NumericRole.INPUT_OPERAND
        }
        unexpected = sorted(guarded_numbers - allowed_numbers)
        if unexpected:
            return False, (
                "unlisted numeric values conflict with fixed contract "
                "constraints: "
                + ", ".join(f"{value:g}" for value in unexpected)
            ), ()

    for constraint in constraints:
        name = str(constraint.get("name") or "unnamed")
        kind = constraint.get("kind")
        groups = constraint.get("evidence_pattern_groups")
        if kind not in {
            "comparison",
            "ordered_boundaries",
            "closed_range",
            "fixed_value",
        }:
            return False, f"unsupported routing constraint kind: {kind}", ()
        if not isinstance(groups, list) or not groups:
            return False, f"routing constraint lacks evidence patterns: {name}", ()

        comparison_binding = None
        if kind == "comparison":
            expected_value = constraint.get("value")
            expected_unit = constraint.get("unit")
            candidates = [
                mention
                for mention in frame.comparisons
                if isinstance(expected_value, (int, float))
                and mention.value == float(expected_value)
                and (
                    expected_unit is None
                    or mention.unit is None
                    or mention.unit == expected_unit
                )
            ]
            if candidates:
                mention = candidates[-1]
                allowed_operators = set(constraint.get(
                    "allowed_operators",
                    (constraint.get("operator"),),
                ))
                if mention.operator not in allowed_operators:
                    return False, (
                        "conflicting comparison operator occurs in fixed "
                        f"contract constraint: {name}"
                    ), ()
                comparison_binding = ComparisonBinding(
                    parameter=str(constraint.get("parameter")),
                    operator=str(mention.operator),
                    value=mention.value,
                    unit=str(expected_unit) if expected_unit else mention.unit,
                    source_span=mention.source_span,
                )

        for group in groups:
            if (
                not isinstance(group, list)
                or not group
                or not all(isinstance(pattern, str) for pattern in group)
            ):
                return False, f"invalid evidence pattern group: {name}", ()
            try:
                matched = any(
                    _pattern_has_positive_match(pattern, question)
                    for pattern in group
                )
            except re.error:
                return False, f"invalid evidence regex in constraint: {name}", ()
            if not matched and comparison_binding is None:
                return False, f"fixed contract constraint is unproven: {name}", ()

        if (
            kind == "comparison"
            and comparison_binding is None
            and _comparison_operator_conflict(
                question,
                str(constraint.get("operator")),
                constraint.get("value"),
            )
        ):
            return False, (
                "conflicting comparison operator occurs in fixed contract "
                f"constraint: {name}"
            ), ()

        conflict_groups = constraint.get("conflict_pattern_groups", ())
        try:
            conflict = any(
                any(
                    _pattern_has_positive_match(pattern, question)
                    for pattern in group
                )
                for group in conflict_groups
            )
        except (re.error, TypeError):
            return False, f"invalid conflict pattern in constraint: {name}", ()
        if conflict:
            return False, f"conflicting contract constraint occurs: {name}", ()
        if comparison_binding is not None:
            bindings.append(comparison_binding)
    return True, "fixed contract constraints passed", tuple(bindings)


def _routing_constraints_hold(
    question: str,
    entry: dict,
) -> tuple[bool, str]:
    holds, reason, _bindings = _bind_routing_constraints(question, entry)
    return holds, reason


def _lexical_aliases_hold(question: str, entry: dict) -> bool:
    """Admit only Skill-declared, high-precision paraphrase patterns."""
    groups = entry.get("lexical_pattern_groups")
    if not groups:
        return False
    try:
        return all(
            isinstance(group, list)
            and bool(group)
            and all(isinstance(pattern, str) for pattern in group)
            and any(
                _pattern_has_positive_match(pattern, question)
                for pattern in group
            )
            for group in groups
        )
    except re.error:
        return False


def validate_semantic_proposal(
    question: str,
    proposal: dict,
    catalog: tuple[dict, ...] | None = None,
) -> RoutingDecision:
    """Fail closed unless every Skill-owned routing concept is grounded."""
    catalog = catalog or _routing_catalog()
    contract_id = proposal.get("contract_id")
    if contract_id is None:
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            0.0,
            str(proposal.get("reason") or "semantic router abstained"),
        )
    entry = next(
        (item for item in catalog if item["id"] == contract_id),
        None,
    )
    if entry is None:
        return RoutingDecision(
            None, RoutingPath.ABSTAIN, 0.0, "unknown semantic contract id"
        )
    boundary_ok, boundary_reason = _request_boundary_holds(question)
    if not boundary_ok:
        return RoutingDecision(
            None, RoutingPath.ABSTAIN, 0.0, boundary_reason
        )
    terms_ok, terms_reason = _contract_terms_hold(question, entry)
    if not terms_ok:
        return RoutingDecision(
            None, RoutingPath.ABSTAIN, 0.0, terms_reason
        )
    if not _critical_anchors_hold(question, entry):
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            0.0,
            "critical contract anchors are absent or excluded anchors occur",
        )
    constraints_ok, constraints_reason, parameter_bindings = (
        _bind_routing_constraints(question, entry)
    )
    if not constraints_ok:
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            0.0,
            constraints_reason,
        )
    try:
        confidence = float(proposal.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    if (
        not math.isfinite(confidence)
        or confidence < _MIN_CONFIDENCE
        or confidence > 1.0
    ):
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            confidence,
            "semantic confidence is outside the accepted finite range",
        )
    evidence = proposal.get("term_evidence")
    if not isinstance(evidence, dict):
        return RoutingDecision(
            None, RoutingPath.ABSTAIN, confidence, "missing term_evidence"
        )
    required = tuple(entry["routing_concepts_all"])
    any_terms = tuple(entry["routing_concepts_any"])
    missing = [
        term for term in required
        if (
            term not in evidence
            or not _quote_is_grounded(question, evidence[term])
            or not _quote_expresses_concept(
                entry,
                term,
                str(evidence[term]),
            )
        )
    ]
    grounded_any = [
        term for term in any_terms
        if (
            term in evidence
            and _quote_is_grounded(question, evidence[term])
            and _quote_expresses_concept(
                entry,
                term,
                str(evidence[term]),
            )
        )
    ]
    if missing or (any_terms and not grounded_any):
        details = []
        if missing:
            details.append("missing grounded terms: " + ", ".join(missing))
        if any_terms and not grounded_any:
            details.append("no grounded one-of term")
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            confidence,
            "; ".join(details),
        )
    allowed_negated_concepts = {
        str(term)
        for term in entry.get("allowed_negated_concepts", ())
    }
    negated = [
        term for term in (*required, *grounded_any)
        if term not in allowed_negated_concepts
        and _quote_is_negated(question, str(evidence[term]))
    ]
    if negated:
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            confidence,
            "semantic evidence is explicitly negated: "
            + ", ".join(negated),
        )
    admitted_quotes = [
        str(evidence[term]).strip().casefold()
        for term in (*required, *grounded_any)
    ]
    if len(admitted_quotes) > 1 and len(set(admitted_quotes)) < 2:
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            confidence,
            "one evidence span cannot prove every routing concept",
        )
    admitted = tuple(
        (term, str(evidence[term]).strip())
        for term in (*required, *grounded_any)
    )
    return RoutingDecision(
        str(contract_id),
        RoutingPath.SEMANTIC,
        confidence,
        str(proposal.get("reason") or "semantic proposal passed hard gate"),
        admitted,
        parameter_bindings=parameter_bindings,
    )


def route_metric_contract(
    question: str,
    *,
    semantic: bool = True,
    resolver: SemanticResolver | None = None,
    on_semantic_call: Callable[[], None] | None = None,
) -> RoutingDecision:
    """Keep exact matching fast; invoke semantics only after lexical abstain."""
    catalog = _routing_catalog()
    boundary_ok, boundary_reason = _request_boundary_holds(question)
    if not boundary_ok:
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            0.0,
            boundary_reason,
        )
    literal_ids = {
        item["id"] for item in matching_metric_contracts(question)
    }
    literal_ids.update(
        item["id"] for item in catalog
        if _lexical_aliases_hold(question, item)
    )
    literal_matches = [
        (metric_contract_by_id(item["id"]), item)
        for item in catalog
        if item["id"] in literal_ids
        and _contract_terms_hold(question, item)[0]
        and _critical_anchors_hold(question, item)
        and _routing_constraints_hold(question, item)[0]
    ]
    literal_matches = [
        (contract, entry)
        for contract, entry in literal_matches
        if contract is not None
    ]
    if len(literal_matches) == 1:
        literal, entry = literal_matches[0]
        _holds, _reason, parameter_bindings = _bind_routing_constraints(
            question,
            entry,
        )
        return RoutingDecision(
            literal["id"],
            RoutingPath.LEXICAL,
            1.0,
            "literal question_terms_all/any matched",
            parameter_bindings=parameter_bindings,
        )
    if not semantic:
        return RoutingDecision(
            None, RoutingPath.ABSTAIN, 0.0, "lexical selector abstained"
        )
    if resolver is None and not config.OPENROUTER_API_KEY:
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            0.0,
            "semantic router unavailable: OPENROUTER_API_KEY is not set",
        )
    semantic_resolver = resolver or openrouter_semantic_resolver
    try:
        if on_semantic_call is not None:
            on_semantic_call()
        proposal = semantic_resolver(question, catalog)
    except RuntimeBudgetExhausted:
        raise
    except Exception as error:
        return RoutingDecision(
            None,
            RoutingPath.ABSTAIN,
            0.0,
            f"semantic router unavailable: {type(error).__name__}",
            semantic_attempted=True,
        )
    return replace(
        validate_semantic_proposal(question, proposal, catalog),
        semantic_attempted=True,
    )

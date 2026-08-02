"""Deterministic numeric intent roles for contract routing.

This module does not choose a business contract. It prevents the router from
confusing thresholds with operands, years, or identifiers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class NumericRole(str, Enum):
    THRESHOLD = "threshold"
    INPUT_OPERAND = "input_operand"
    TIME_PERIOD = "time_period"
    IDENTIFIER = "identifier"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class NumericMention:
    value: float
    role: NumericRole
    source_span: str
    start: int
    end: int
    operator: str | None = None
    unit: str | None = None


@dataclass(frozen=True)
class ComparisonBinding:
    parameter: str
    operator: str
    value: float
    unit: str | None
    source_span: str


@dataclass(frozen=True)
class IntentFrame:
    numeric_mentions: tuple[NumericMention, ...]

    @property
    def comparisons(self) -> tuple[NumericMention, ...]:
        return tuple(
            mention
            for mention in self.numeric_mentions
            if mention.role is NumericRole.THRESHOLD
            and mention.operator is not None
        )


_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
_PERCENT_AFTER = re.compile(r"^\s*(?:%|เปอร์เซ็นต์)", re.IGNORECASE)
_TIME_CONTEXT = re.compile(
    r"(?:ปี|ค\.ศ\.|พ\.ศ\.|year|review[_\s-]*period|issue[_\s-]*d)",
    re.IGNORECASE,
)
_OPERAND_CONTEXT = re.compile(
    r"(?:มี|จำนวน|ทั้งหมด|รวม|นับ|count|total)[^\n.!?]{0,28}$|"
    r"^\s*(?:คน|ราย|รายการ|records?|employees?|applications?)\b",
    re.IGNORECASE,
)
_IDENTIFIER_CONTEXT = re.compile(
    r"(?:top|อันดับ|สูงสุด)\s*$|^\s*(?:อันดับ|รายการแรก)",
    re.IGNORECASE,
)
_THRESHOLD_CONTEXT = re.compile(
    r"(?:เกณฑ์|เป้า(?:หมาย)?|นโยบาย|limit|threshold|target|benchmark|"
    r"concentration)",
    re.IGNORECASE,
)
_OPERATORS = (
    (
        "gte",
        re.compile(
            r">=|=>|ไม่น้อยกว่า|ไม่ต่ำกว่า|อย่างน้อย|ขั้นต่ำ|"
            r"สูงถึง(?:เป้า(?:หมาย)?)?|ถึงเป้า(?:หมาย)?|"
            r"\bat\s+least\b",
            re.IGNORECASE,
        ),
    ),
    (
        "lte",
        re.compile(
            r"<=|=<|ไม่เกิน|ไม่มากกว่า|ไม่สูงกว่า|อย่างมาก|"
            r"\bat\s+most\b",
            re.IGNORECASE,
        ),
    ),
    (
        "gt",
        re.compile(
            r">(?!=)|(?<!ไม่)มากกว่า|(?<!ไม่)เกิน|(?<!ไม่)สูงกว่า|"
            r"\b(?:greater|more|higher)\s+than\b",
            re.IGNORECASE,
        ),
    ),
    (
        "lt",
        re.compile(
            r"<(?!=)|(?<!ไม่)น้อยกว่า|(?<!ไม่)ต่ำกว่า|"
            r"\b(?:less|lower)\s+than\b",
            re.IGNORECASE,
        ),
    ),
    (
        "eq",
        re.compile(
            r"==|(?<![<>])=(?!=)|เท่ากับ|เท่ากัน|\bequal(?:\s+to)?\b",
            re.IGNORECASE,
        ),
    ),
)


def _nearest_operator(context: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    for operator, pattern in _OPERATORS:
        for match in pattern.finditer(context):
            candidates.append((match.start(), operator))
    return max(candidates)[1] if candidates else None


def analyze_intent_frame(question: str) -> IntentFrame:
    mentions = []
    for match in _NUMBER.finditer(question):
        value = float(match.group(0).replace(",", ""))
        before = question[max(0, match.start() - 96):match.start()]
        after = question[match.end():match.end() + 48]
        local = question[max(0, match.start() - 64):match.end() + 32]
        percent = bool(_PERCENT_AFTER.match(after))
        operator = _nearest_operator(before)

        if 1900 <= value <= 2200 and _TIME_CONTEXT.search(local) and not percent:
            role, unit, operator = NumericRole.TIME_PERIOD, "year", None
        elif _IDENTIFIER_CONTEXT.search(before[-24:] + after[:24]):
            role, unit, operator = NumericRole.IDENTIFIER, None, None
        elif percent or (operator is not None and _THRESHOLD_CONTEXT.search(local)):
            role = NumericRole.THRESHOLD
            unit = "percent" if percent else None
        elif (
            _OPERAND_CONTEXT.search(before[-64:])
            or _OPERAND_CONTEXT.search(after[:32])
        ):
            role, unit, operator = NumericRole.INPUT_OPERAND, None, None
        else:
            role, unit = NumericRole.UNCLASSIFIED, None

        mentions.append(NumericMention(
            value=value,
            role=role,
            source_span=local.strip(),
            start=match.start(),
            end=match.end(),
            operator=operator,
            unit=unit,
        ))
    return IntentFrame(tuple(mentions))

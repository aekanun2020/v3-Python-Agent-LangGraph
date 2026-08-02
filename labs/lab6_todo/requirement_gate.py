"""Small pre-tool gate for explicitly declared multi-condition requests."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RequirementAssessment:
    complete: bool
    declared_count: int | None
    detected_count: int
    reason: str


_DECLARED_TWO = re.compile(
    r"(?:ทั้งสอง|2|two|both)\s*"
    r"(?:เงื่อนไข|เกณฑ์|ตัวชี้วัด|conditions?|criteria|requirements?|metrics?)",
    flags=re.IGNORECASE,
)
_META_DECLARATION = re.compile(
    r"(?:และ|โดย)?\s*"
    r"(?:ต้อง)?(?:ผ่าน|ครบ|ตรงตาม|meet|pass|satisfy)?\s*"
    r"(?:ทั้งสอง|2|two|both)\s*"
    r"(?:เงื่อนไข|เกณฑ์|ตัวชี้วัด|conditions?|criteria|requirements?|metrics?)",
    flags=re.IGNORECASE,
)
_COMPARISON = re.compile(
    r">(?!=)|<(?!=)|>=|<=|สูงกว่า|ต่ำกว่า|มากกว่า|น้อยกว่า|ไม่น้อยกว่า|"
    r"ไม่เกิน|เท่ากับ|above|below|greater\s+than|less\s+than|"
    r"at\s+least|at\s+most|equal\s+to",
    flags=re.IGNORECASE,
)
_SHARED_COMPARISON_THAI = re.compile(
    r"ทั้ง\s*(?P<left>[^\n.!?]{2,80}?)\s*และ\s*"
    r"(?P<right>[^\n.!?]{2,100}?)"
    r"(?:สูงกว่า|ต่ำกว่า|มากกว่า|น้อยกว่า|ไม่น้อยกว่า|ไม่เกิน|เท่ากับ)",
    flags=re.IGNORECASE,
)
_SHARED_COMPARISON_ENGLISH = re.compile(
    r"\bboth\s+(?P<left>[^\n.!?]{2,80}?)\s+and\s+"
    r"(?P<right>[^\n.!?]{2,100}?)\s+"
    r"(?:are\s+)?(?:above|below|greater\s+than|less\s+than|equal\s+to)",
    flags=re.IGNORECASE,
)


def assess_requirement_completeness(question: str) -> RequirementAssessment:
    """Fail only when the request explicitly promises two but supplies one."""
    if not _DECLARED_TWO.search(question):
        return RequirementAssessment(
            complete=True,
            declared_count=None,
            detected_count=0,
            reason="no explicit multi-condition declaration",
        )

    body = _META_DECLARATION.sub(" ", question)
    comparison_count = len(_COMPARISON.findall(body))
    shared_pair = bool(
        _SHARED_COMPARISON_THAI.search(body)
        or _SHARED_COMPARISON_ENGLISH.search(body)
    )
    detected = max(comparison_count, 2 if shared_pair else 0)
    if detected >= 2:
        return RequirementAssessment(
            complete=True,
            declared_count=2,
            detected_count=detected,
            reason="two independently stated or coordinated conditions found",
        )
    return RequirementAssessment(
        complete=False,
        declared_count=2,
        detected_count=detected,
        reason=(
            "คำถามระบุว่าต้องผ่านสองเงื่อนไข แต่พบเงื่อนไขเปรียบเทียบที่ระบุชัดเพียง "
            f"{detected} เงื่อนไข; กรุณาระบุเงื่อนไขที่สองก่อนเรียก tool"
        ),
    )

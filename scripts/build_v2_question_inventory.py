"""Freeze every externally executed question recorded by the v2 repository.

The inventory deliberately reads question/prompt/user_question fields from
versioned JSON evaluation manifests and run artifacts.  Internal unit-test
fragments are excluded because they were verifier inputs, not questions sent to
the agent.  Source files remain attached to every deduplicated question.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


QUESTION_KEYS = {"question", "prompt", "user_question"}
HR_CONTRACTS = (
    "active_headcount_by_department",
    "active_employment_mix_by_department",
    "strict_contract_dependency_policy",
    "performance_review_coverage",
    "training_hours_portfolio",
    "training_certificate_semantic_separation",
    "expert_skill_record_share",
    "top_two_project_concentration",
    "project_value_per_active_employee",
    "staffing_decision_insufficient",
)
FINANCE_CONTRACTS = (
    "finance_portfolio_totals",
    "finance_application_mix",
    "finance_status_mix",
    "finance_year_cohorts",
    "finance_home_ownership_segments",
    "finance_employment_extrema",
    "finance_dti_buckets",
    "finance_fixed_income_bands",
    "finance_funding_gap_by_year",
    "finance_dual_risk_screen",
)

# The original frozen-v1 routing suite contained five expectation defects.
# Later semantic-v2/v3 corrections fixed them by changing the questions.  This
# inventory keeps the historical questions, so it records the semantically
# audited disposition of those original strings instead.
AUDITED_ORIGINAL_DISPOSITIONS = {
    "ควรลดคนหรือเพิ่มคนจาก headcount เพียงอย่างเดียวหรือไม่": (
        "staffing_decision_insufficient",
        "later audit: unsupported staffing decision belongs to the refusal contract",
    ),
    "คัดช่วงอายุงานที่สัดส่วน Charged Off สูงกว่าค่าเฉลี่ยรวมแบบ strict และผ่านทั้งสองเงื่อนไข": (
        None,
        "later audit: original question omitted the int_rate condition",
    ),
    "ตรวจ performance review coverage รายฝ่ายเทียบเกณฑ์ 80%": (
        None,
        "later audit: original grain/period did not match the organization-2023 contract",
    ),
    "เฉพาะผู้สมัครเดี่ยว แบ่งช่วงรายได้คงที่สี่ช่วงตั้งแต่ต่ำกว่า 50000 ถึง 100000 ขึ้นไป": (
        None,
        "later audit: original question omitted intermediate fixed boundaries",
    ),
    "โครงการสองรายการแรกกินสัดส่วนมูลค่ารวมเกินหกสิบเปอร์เซ็นต์หรือไม่": (
        None,
        "later audit: first two records do not prove top-two-by-project_value",
    ),
}

# These were repeatedly executed manually during v2 development but were not
# copied into the structured evaluation JSON.  One remains in the versioned
# README; the other is preserved from the v2 development conversation supplied
# by the repository owner.  Keep them after the JSON-derived ids so expanding
# manual provenance cannot renumber the frozen 61-case core.
MANUAL_HISTORY_CASES = (
    {
        "question": "นับพนักงานที่ยังปฏิบัติงานแยกตามแผนก",
        "expected_contract": "active_headcount_by_department",
        "category": "v2_manual_history",
        "historical_suite_id": "manual_active_headcount",
        "provenance": [
            {
                "file": "README.md",
                "json_path": "markdown command example at source commit",
            },
            {
                "file": "labs/lab6_todo/README.md",
                "json_path": "markdown command example at source commit",
            },
        ],
    },
    {
        "question": "ระยะเวลาการทำงานที่มีผลต่อการอนุมัติวงเงิน",
        "expected_contract": None,
        "category": "v2_manual_history",
        "historical_suite_id": "manual_employment_approval_semantics",
        "provenance": [
            {
                "file": "owner-supplied-v2-development-transcript",
                "json_path": "repeated live command; not versioned in repository",
            }
        ],
    },
)


def normalized(value: str) -> str:
    return " ".join(value.split())


def sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def walk_questions(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in QUESTION_KEYS and isinstance(child, str) and child.strip():
                yield normalized(child), child_path
            yield from walk_questions(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_questions(child, f"{path}[{index}]")


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def primary_questions(path: Path, field: str) -> list[dict]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid primary source: {path}")
    values = payload[field]
    return list(values)


def v2_baseline_answers(v2: Path) -> dict[str, str]:
    answers: dict[str, str] = {}
    hr = load_json(v2 / "artifacts" / "hr_skill_q1_q10_run5.json")
    if isinstance(hr, dict):
        question_by_id = {
            item["id"]: normalized(item["question"])
            for item in hr.get("questions", [])
        }
        for item in hr.get("runs", []):
            if item.get("variant") != "phase2c_python_first":
                continue
            question = question_by_id.get(item.get("question_id"))
            if question and item.get("answer"):
                answers[question] = item["answer"]
    finance = load_json(
        v2 / "artifacts" / "finance_mcp_agent_q1_q10_skill_run4.json"
    )
    if isinstance(finance, dict):
        for item in finance.get("records", []):
            if item.get("question") and item.get("answer"):
                answers[normalized(item["question"])] = item["answer"]
    return answers


def build_inventory(v2: Path) -> dict:
    v2 = v2.resolve()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=v2,
        text=True,
    ).strip()
    occurrences: dict[str, list[dict]] = defaultdict(list)
    candidates = sorted((v2 / "artifacts").glob("*.json")) + sorted(
        (v2 / "tests" / "evaluation").glob("*.json")
    )
    for path in candidates:
        payload = load_json(path)
        if payload is None:
            continue
        relative = str(path.relative_to(v2))
        for question, json_path in walk_questions(payload):
            occurrences[question].append({
                "file": relative,
                "json_path": json_path,
            })
    json_questions = set(occurrences)

    for manual in MANUAL_HISTORY_CASES:
        question = normalized(manual["question"])
        if question in occurrences:
            continue
        occurrences[question].extend(manual["provenance"])

    expected: dict[str, str | None] = {}
    categories: dict[str, str] = {}
    suite_ids: dict[str, list[str]] = defaultdict(list)
    eval_dir = v2 / "tests" / "evaluation"
    for path in sorted(eval_dir.glob("*.json")):
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        category = path.stem
        for item in payload.get("cases", []):
            question = normalized(item["question"])
            expected[question] = item.get("expected_contract")
            categories[question] = category
            suite_ids[question].append(item["id"])

    hr_source = v2 / "artifacts" / "hr_skill_q1_q10_run5.json"
    for item, contract in zip(primary_questions(hr_source, "questions"), HR_CONTRACTS):
        question = normalized(item["question"])
        expected.setdefault(question, contract)
        categories.setdefault(question, "hr_primary_q1_q10")
        suite_ids[question].append(item["id"])

    finance_source = (
        v2 / "artifacts" / "finance_mcp_agent_q1_q10_skill_run4.json"
    )
    for item, contract in zip(
        primary_questions(finance_source, "records"),
        FINANCE_CONTRACTS,
    ):
        question = normalized(item["question"])
        expected.setdefault(question, contract)
        categories.setdefault(question, "finance_primary_q1_q10")
        suite_ids[question].append(item["id"])

    # The first finance run used an NTILE(4) question which was later replaced
    # by fixed bands.  It is still historical v2 coverage, but intentionally has
    # no v3 Skill contract and must exercise the general path.
    for question in occurrences:
        if "NTILE(4)" in question:
            expected.setdefault(question, None)
            categories.setdefault(question, "finance_legacy_general")
            suite_ids[question].append("Q08_NTILE_legacy")

    audit_notes: dict[str, str] = {}
    for question, (contract, reason) in AUDITED_ORIGINAL_DISPOSITIONS.items():
        if question not in occurrences:
            raise ValueError(f"audited original question is absent: {question}")
        expected[question] = contract
        audit_notes[question] = reason

    for manual in MANUAL_HISTORY_CASES:
        question = normalized(manual["question"])
        expected.setdefault(question, manual["expected_contract"])
        categories.setdefault(question, manual["category"])
        suite_ids[question].append(manual["historical_suite_id"])

    baseline_answers = v2_baseline_answers(v2)
    cases = []
    ordered_questions = sorted(json_questions)
    ordered_questions.extend(
        normalized(item["question"])
        for item in MANUAL_HISTORY_CASES
        if normalized(item["question"]) not in json_questions
    )
    for index, question in enumerate(ordered_questions, start=1):
        if question not in expected:
            raise ValueError(f"question has no expected disposition: {question}")
        contract = expected[question]
        provenance = sorted(
            occurrences[question],
            key=lambda item: (item["file"], item["json_path"]),
        )
        baseline_answer = baseline_answers.get(question)
        cases.append({
            "id": f"v2q_{index:03d}",
            "question": question,
            "category": categories[question],
            "historical_suite_ids": sorted(set(suite_ids[question])),
            "expected_contract": contract,
            "expectation_audit_note": audit_notes.get(question),
            "evaluation_mode": (
                "contract_live" if contract else "general_agent_live"
            ),
            "v2_baseline_answer_sha256": (
                hashlib.sha256(baseline_answer.encode("utf-8")).hexdigest()
                if baseline_answer else None
            ),
            "provenance_count": len(provenance),
            "provenance": provenance,
        })
    projection = [
        {
            "id": item["id"],
            "question": item["question"],
            "expected_contract": item["expected_contract"],
            "evaluation_mode": item["evaluation_mode"],
        }
        for item in cases
    ]
    return {
        "suite_id": "v2-full-question-replay-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frozen_before_first_run": True,
        "source_repository": "aekanun2020/v2-Python-Agent-LangGraph",
        "source_commit": commit,
        "scope": (
            "Deduplicated external agent questions stored under "
            "artifacts/*.json and tests/evaluation/*.json. Internal unit-test "
            "verifier fragments are excluded."
        ),
        "question_count": len(cases),
        "contract_live_count": sum(
            item["evaluation_mode"] == "contract_live" for item in cases
        ),
        "general_agent_live_count": sum(
            item["evaluation_mode"] == "general_agent_live" for item in cases
        ),
        "question_projection_sha256": sha256(projection),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = build_inventory(args.v2_repo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} questions={inventory['question_count']} "
        f"projection={inventory['question_projection_sha256']}"
    )


if __name__ == "__main__":
    main()

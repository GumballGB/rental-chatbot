# Compare final extracted fields; intermediate turns are never scored.

import unicodedata

from core.store import normalize_phone
from eval.chatbot.cases import (
    SCORED_FIELDS,
    index_records,
    validate_answers,
)


def _ratio(correct: int, total: int) -> float | None:
    return correct / total if total else None


def _normalize(field: str, value):
    if not isinstance(value, str):
        return value
    value = unicodedata.normalize("NFC", value).strip()
    if field == "email":
        return value.casefold()
    if field == "phone":
        return normalize_phone(value)
    return value


def calculate_metrics(
    expected_answers: list[dict], predictions: list[dict], *, conversations: list[dict] | None = None,
) -> dict:
    """Score six fields and the final refusal set, matching cases by ID.

    Missing/failed extractions stay in all accuracy denominators. Field accuracy
    counts correct nulls; supplied-value accuracy considers only expected nonnull
    fields. Keep unexpected values, omissions and wrong supplied values visible.
    Summary message wording and application-generated fields are not scored.
    Optional conversation metadata adds paired-consistency scores.
    """

    expected_by_id = validate_answers(expected_answers)
    predicted_by_id = index_records(predictions, "prediction")
    unknown = set(predicted_by_id) - set(expected_by_id)
    if unknown:
        raise ValueError(f"Unknown prediction conversation IDs: {', '.join(sorted(unknown))}")
    per_field = {
        field: {"correct": 0, "correct_values": 0, "expected_values": 0,
                "invented": 0, "omitted": 0, "wrong": 0}
        for field in SCORED_FIELDS
    }
    correct = declined_correct = 0
    failures = []
    cases = []
    for conversation_id, answer in expected_by_id.items():
        expected = answer["expected"]
        prediction = predicted_by_id.get(conversation_id)
        if prediction is None:
            error = "No extraction recorded."
            extracted = None
        else:
            extracted = prediction.get("extracted")
            error = prediction.get("error")
            if not error and not isinstance(extracted, dict):
                error = "No extraction returned."
        mismatches = {}
        if error:
            failures.append({"conversation_id": conversation_id, "error": error})
        for field in SCORED_FIELDS:
            stats = per_field[field]
            wanted = expected[field]
            stats["expected_values"] += wanted is not None
            if error:
                continue
            actual = extracted.get(field)
            if _normalize(field, actual) == _normalize(field, wanted):
                stats["correct"] += 1
                stats["correct_values"] += wanted is not None
            else:
                category = "invented" if wanted is None else "omitted" if actual is None else "wrong"
                stats[category] += 1
                mismatches[field] = {"expected": wanted, "actual": actual}
        if not error:
            actual_declined = extracted.get("declined_fields")
            refusal_match = (
                isinstance(actual_declined, list)
                and all(isinstance(field, str) for field in actual_declined)
                and set(actual_declined) == set(expected["declined_fields"])
            )
            declined_correct += refusal_match
            if not refusal_match:
                mismatches["declined_fields"] = {"expected": expected["declined_fields"], "actual": actual_declined}
        exact = not error and not mismatches
        correct += exact
        cases.append({"conversation_id": conversation_id, "correct": exact,
                      "mismatches": mismatches, "error": error})

    total = len(expected_by_id)
    for stats in per_field.values():
        stats["accuracy"] = _ratio(stats["correct"], total)
        stats["supplied_accuracy"] = _ratio(stats["correct_values"], stats["expected_values"])
        stats["failed"] = len(failures)
    report = {
        "total": total, "correct": correct, "accuracy": _ratio(correct, total),
        "failed": len(failures), "per_field": per_field,
        "declined_fields": {"correct": declined_correct, "accuracy": _ratio(declined_correct, total)},
        "failures": failures, "cases": cases,
    }
    if conversations is not None:
        _add_pair_scores(report, conversations, expected_answers, predictions)
    return report


def _same_final_fields(left: dict, right: dict) -> bool:
    """Compare pair outputs with exactly the field rules used for accuracy."""
    if any(_normalize(field, left.get(field)) != _normalize(field, right.get(field)) for field in SCORED_FIELDS):
        return False
    refusals = [result.get("declined_fields") for result in (left, right)]
    if not all(isinstance(items, list) and all(isinstance(item, str) for item in items) for items in refusals):
        return False
    return set(refusals[0]) == set(refusals[1])


def _add_pair_scores(report: dict, conversations: list[dict], answers: list[dict], predictions: list[dict]) -> None:
    """Compare complete pairs within the same evaluation set."""
    by_id = index_records(conversations, "conversation")
    if set(by_id) != {answer["conversation_id"] for answer in answers}:
        raise ValueError("Conversation metadata must cover exactly the scored cases.")
    pairs = {}
    for case in conversations:
        if "pair_id" in case:
            pairs.setdefault(case["pair_id"], []).append(case["conversation_id"])
    predicted_by_id = index_records(predictions, "prediction")
    scored_by_id = {case["conversation_id"]: case for case in report["cases"]}
    pair_results = []
    not_evaluated = 0
    for pair_id, ids in pairs.items():
        if len(ids) == 1:
            # A --limit selection may include only one half of a valid pair.
            not_evaluated += 1
            continue
        if len(ids) != 2:
            raise ValueError("A consistency pair must have exactly two conversations.")
        valid = all(not scored_by_id[conversation_id]["error"] for conversation_id in ids)
        consistent = valid and _same_final_fields(*(predicted_by_id[conversation_id]["extracted"] for conversation_id in ids))
        pair_results.append({
            "pair_id": pair_id, "conversation_ids": ids, "consistent": consistent,
            "both_correct": all(scored_by_id[conversation_id]["correct"] for conversation_id in ids),
        })
    consistent = sum(pair["consistent"] for pair in pair_results)
    report["paired_consistency"] = {
        "total": len(pair_results), "consistent": consistent,
        "consistency_rate": _ratio(consistent, len(pair_results)),
        "both_correct": sum(pair["both_correct"] for pair in pair_results),
        "not_evaluated": not_evaluated, "cases": pair_results,
    }

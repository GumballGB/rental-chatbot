"""Check answer-key integrity without treating proposed labels as model results."""

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import get_args

import pytest

from core.store import JsonStore
from models.enquiry import Enquiry
from models.recommendation import Label

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def dataset():
    enquiries = json.loads((DATA_DIR / "unit_enquiries.json").read_text(encoding="utf-8"))
    answers = json.loads((DATA_DIR / "enquiry_recommendation_ground_truth.json").read_text(encoding="utf-8"))
    return enquiries, answers


def test_answer_key_covers_100_unique_enquiries(dataset):
    enquiries, answers = dataset
    expected_ids = {f"ENQ-{index:03d}" for index in range(1, 101)}

    assert len(enquiries) == len(answers) == 100
    assert {row["enquiry_id"] for row in enquiries} == expected_ids
    assert {row["enquiry_id"] for row in answers} == expected_ids
    for answer in answers:
        assert answer["expected_label"] in get_args(Label)
        assert answer["rationale"].strip()
        if answer["expected_label"] != "duplicate":
            assert answer["expected_duplicated_enquiry_id"] is None


def test_all_four_classes_have_at_least_20_examples(dataset):
    _, answers = dataset
    counts = Counter(answer["expected_label"] for answer in answers)

    for label in get_args(Label):
        assert counts[label] >= 20, f"Too few {label} cases: {counts[label]}"


def test_completeness_labels_follow_the_agreed_structured_field_rule(dataset):
    enquiries, answers = dataset
    by_id = {row["enquiry_id"]: row for row in enquiries}

    for answer in answers:
        if answer["expected_label"] not in {"genuine", "needs_info"}:
            continue
        row = by_id[answer["enquiry_id"]]
        has_name = bool((row["name"] or "").strip())
        has_contact = bool((row["email"] or "").strip() or (row["phone"] or "").strip())
        expected = "genuine" if has_name and has_contact else "needs_info"
        assert answer["expected_label"] == expected, answer["enquiry_id"]


def test_duplicate_targets_are_earlier_and_reachable_by_the_real_tool(dataset):
    _, answers = dataset
    store = JsonStore(DATA_DIR)

    for answer in answers:
        if answer["expected_label"] != "duplicate":
            continue
        current = store.get_enquiry(answer["enquiry_id"])
        target = store.get_enquiry(answer["expected_duplicated_enquiry_id"])
        assert target.enquiry_id != current.enquiry_id
        assert date.fromisoformat(target.received_date) < date.fromisoformat(current.received_date)
        candidates = store.find_duplicate_enquiry_candidates(
            exclude_enquiry_id=current.enquiry_id, received_before=current.received_date,
            email=current.email, phone=current.phone, name=current.name,
            listing_id=current.listing_id, move_in_date=current.move_in_date,
        )
        assert target.enquiry_id in {candidate.enquiry_id for candidate, _ in candidates}, answer["enquiry_id"]


def test_added_cases_cannot_change_the_original_duplicate_context(dataset):
    enquiries, _ = dataset
    original = enquiries[:47]
    additions = enquiries[47:]
    latest_original = max(date.fromisoformat(row["received_date"]) for row in original)

    assert len(additions) == 53
    assert all(date.fromisoformat(row["received_date"]) > latest_original for row in additions)


def test_input_rows_contain_only_enquiry_fields_and_valid_listing_currencies(dataset):
    enquiries, _ = dataset
    store = JsonStore(DATA_DIR)

    for row in enquiries:
        assert set(row) <= set(Enquiry.model_fields), row["enquiry_id"]
        if row["listing_id"] and row["budget_currency"]:
            assert store.get_listing(row["listing_id"]).currency == row["budget_currency"], row["enquiry_id"]

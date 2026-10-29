"""The evaluation examples must cover both sides of the contact policy."""

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(("label", "has_name", "has_email", "has_phone"), [
    ("genuine", True, False, True),
    ("needs_info", False, True, True),
])
def test_dataset_covers_contact_policy_edges(label, has_name, has_email, has_phone):
    root = Path(__file__).resolve().parents[2] / "data"
    enquiries = json.loads((root / "unit_enquiries.json").read_text(encoding="utf-8"))
    answers = json.loads((root / "enquiry_recommendation_ground_truth.json").read_text(encoding="utf-8"))
    expected = {answer["enquiry_id"]: answer["expected_label"] for answer in answers}

    assert any(
        expected[enquiry["enquiry_id"]] == label
        and bool(enquiry["name"]) == has_name
        and bool(enquiry["email"]) == has_email
        and bool(enquiry["phone"]) == has_phone
        for enquiry in enquiries
    ), f"Missing {label} case: name={has_name}, email={has_email}, phone={has_phone}"

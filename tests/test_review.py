# Tests for the Review model (HITL human review of rental enquiries)

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from models.review import Review


def review_data(**overrides):
    data = {
        "enquiry_id": "ENQ-001",
        "run_id": uuid4(),
        "recommended_label": "genuine",
        "decision": "pending",
    }
    return {**data, **overrides}


def test_pending_review_has_no_decision_metadata():
    review = Review(**review_data())

    assert review.final_label is None
    assert review.reviewer is None
    assert review.review_date is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("final_label", "genuine"),
        ("reviewer", "reviewer@example.com"),
        ("review_date", datetime.now(UTC)),
    ],
)
def test_pending_review_rejects_decision_metadata(field, value):
    with pytest.raises(ValidationError):
        Review(**review_data(**{field: value}))


def test_approved_review_uses_recommended_label():
    review = Review(
        **review_data(
            decision="approved",
            final_label="genuine",
            reviewer="reviewer@example.com",
            review_date=datetime.now(UTC),
        )
    )

    assert review.final_label == review.recommended_label


def test_approved_review_rejects_different_label():
    with pytest.raises(ValidationError, match="must equal recommended outcome"):
        Review(
            **review_data(
                decision="approved",
                final_label="spam",
                reviewer="reviewer@example.com",
                review_date=datetime.now(UTC),
            )
        )


@pytest.mark.parametrize("missing_field", ["reviewer", "review_date"])
def test_decided_review_requires_reviewer_and_timestamp(missing_field):
    decision_data = review_data(
        decision="approved",
        final_label="genuine",
        reviewer="reviewer@example.com",
        review_date=datetime.now(UTC),
    )
    decision_data[missing_field] = None

    with pytest.raises(ValidationError, match="required for a decided review"):
        Review(**decision_data)


def test_overridden_review_requires_final_label_and_message():
    with pytest.raises(ValidationError, match="final_label is required"):
        Review(
            **review_data(
                decision="overridden",
                reviewer="reviewer@example.com",
                review_date=datetime.now(UTC),
                message="Manual correction.",
            )
        )

    with pytest.raises(ValidationError, match="message is required"):
        Review(
            **review_data(
                decision="overridden",
                final_label="needs_info",
                reviewer="reviewer@example.com",
                review_date=datetime.now(UTC),
            )
        )


def test_overridden_review_accepts_reasoned_label_change():
    review = Review(
        **review_data(
            decision="overridden",
            final_label="needs_info",
            reviewer="reviewer@example.com",
            review_date=datetime.now(UTC),
            message="The renter must provide a move-in date.",
        )
    )

    assert review.final_label == "needs_info"


def test_overridden_review_rejects_unchanged_label():
    with pytest.raises(ValidationError, match="must differ from recommended outcome"):
        Review(
            **review_data(
                decision="overridden",
                final_label="genuine",
                reviewer="reviewer@example.com",
                review_date=datetime.now(UTC),
                message="Reviewed without changing the model label.",
            )
        )


def test_pending_duplicate_recommendation_requires_duplicate_id():
    review = Review(
        **review_data(
            recommended_label="duplicate",
            recommended_duplicated_enquiry_id="ENQ-000",
        )
    )

    assert review.recommended_duplicated_enquiry_id == "ENQ-000"

    with pytest.raises(
        ValidationError,
        match="recommended_duplicated_enquiry_id is required",
    ):
        Review(**review_data(recommended_label="duplicate"))


def test_approving_duplicate_requires_same_duplicate_id():
    approved_data = review_data(
        recommended_label="duplicate",
        recommended_duplicated_enquiry_id="ENQ-000",
        decision="approved",
        final_label="duplicate",
        final_duplicated_enquiry_id="ENQ-000",
        reviewer="reviewer@example.com",
        review_date=datetime.now(UTC),
    )
    review = Review(**approved_data)

    assert review.final_duplicated_enquiry_id == "ENQ-000"

    approved_data["final_duplicated_enquiry_id"] = "ENQ-002"
    with pytest.raises(ValidationError, match="must equal recommended outcome"):
        Review(**approved_data)


def test_overriding_genuine_to_duplicate_requires_final_duplicate_id():
    with pytest.raises(
        ValidationError,
        match="final_duplicated_enquiry_id is required",
    ):
        Review(
            **review_data(
                decision="overridden",
                final_label="duplicate",
                reviewer="reviewer@example.com",
                review_date=datetime.now(UTC),
                message="This matches an earlier enquiry.",
            )
        )


def test_duplicate_to_different_duplicate_is_valid_override():
    review = Review(
        **review_data(
            recommended_label="duplicate",
            recommended_duplicated_enquiry_id="ENQ-000",
            decision="overridden",
            final_label="duplicate",
            final_duplicated_enquiry_id="ENQ-002",
            reviewer="reviewer@example.com",
            review_date=datetime.now(UTC),
            message="The model selected the wrong original enquiry.",
        )
    )

    assert review.recommended_label == review.final_label
    assert (
        review.recommended_duplicated_enquiry_id
        != review.final_duplicated_enquiry_id
    )


def test_overridden_duplicate_rejects_same_label_and_duplicate_id():
    with pytest.raises(ValidationError, match="must differ from recommended outcome"):
        Review(
            **review_data(
                recommended_label="duplicate",
                recommended_duplicated_enquiry_id="ENQ-000",
                decision="overridden",
                final_label="duplicate",
                final_duplicated_enquiry_id="ENQ-000",
                reviewer="reviewer@example.com",
                review_date=datetime.now(UTC),
                message="No actual change.",
            )
        )


@pytest.mark.parametrize(
    ("recommended_duplicate_id", "final_duplicate_id", "decision"),
    [
        ("ENQ-001", None, "pending"),
        (None, "ENQ-001", "overridden"),
    ],
)
def test_review_rejects_self_duplicate(
    recommended_duplicate_id,
    final_duplicate_id,
    decision,
):
    data = review_data(
        recommended_label=("duplicate" if recommended_duplicate_id else "genuine"),
        recommended_duplicated_enquiry_id=recommended_duplicate_id,
        decision=decision,
    )
    if decision == "overridden":
        data.update(
            final_label="duplicate",
            final_duplicated_enquiry_id=final_duplicate_id,
            reviewer="reviewer@example.com",
            review_date=datetime.now(UTC),
            message="Invalid self-reference.",
        )

    with pytest.raises(ValidationError, match="cannot be a duplicate of itself"):
        Review(**data)

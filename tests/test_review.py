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
    with pytest.raises(ValidationError, match="must equal recommended_label"):
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
    with pytest.raises(ValidationError, match="must differ from recommended_label"):
        Review(
            **review_data(
                decision="overridden",
                final_label="genuine",
                reviewer="reviewer@example.com",
                review_date=datetime.now(UTC),
                message="Reviewed without changing the model label.",
            )
        )

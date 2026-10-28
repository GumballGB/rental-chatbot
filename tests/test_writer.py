# Runtime persistence keeps complete bodies and publishes pending reviews last.

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core import writer

# The models
from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review
from models.triage_result import TriageResult


@pytest.fixture
def enquiry():
    return Enquiry(
        enquiry_id="ENQ-new",
        name="Amélie",
        email="amelie@example.com",
        phone="+1 514 555 0123",
        message="I am looking for a studio in Montréal.",
        budget=1900,
        budget_currency="CAD",
        listing_id="LST-001",
        received_date="2026-10-28",
    )


@pytest.fixture
def result(enquiry):
    return TriageResult(
        run_id=uuid4(),
        recommendation=Recommendation(
            referred_enquiry_id=enquiry.enquiry_id,
            label="duplicate",
            duplicated_enquiry_id="ENQ-earlier",
            reason="Matches an earlier enquiry.",
            evidence=[{
                "source": "message",
                "quote": "looking for a studio in Montréal",
                "support": "States the same rental intent.",
            }],
        ),
    )


def test_save_for_review_preserves_both_bodies_and_links(tmp_path, enquiry, result):
    review = writer.save_for_review(enquiry, result, tmp_path)

    enquiry_path = tmp_path / "enquiries" / f"{enquiry.enquiry_id}.json"
    recommendation_path = tmp_path / "recommendations" / f"{result.run_id}.json"
    review_path = tmp_path / "reviews" / enquiry.enquiry_id / f"{result.run_id}.json"

    # The enquiry and recommendation are saved as-is.
    assert Enquiry.model_validate_json(enquiry_path.read_text(encoding="utf-8")) == enquiry
    assert Recommendation.model_validate_json(
        recommendation_path.read_text(encoding="utf-8")
    ) == result.recommendation

    # The review is saved and links the two bodies together.
    assert Review.model_validate_json(review_path.read_text(encoding="utf-8")) == review
    assert review.enquiry_id == enquiry.enquiry_id
    assert review.run_id == result.run_id
    assert review.decision == "pending"
    assert review.recommended_label == "duplicate"
    assert review.recommended_duplicated_enquiry_id == "ENQ-earlier"
    assert review.final_label is None
    assert '\n  "name": "Amélie"' in enquiry_path.read_text(encoding="utf-8")
    assert len(list(tmp_path.rglob("*.json"))) == 3
    assert not list(tmp_path.rglob("*.tmp"))


@pytest.mark.parametrize("decision", ["approved", "overridden"])
def test_decided_review_replaces_pending_at_same_path(
    tmp_path, enquiry, result, decision,
):
    pending = writer.save_for_review(enquiry, result, tmp_path)
    recommendation_path = tmp_path / "recommendations" / f"{result.run_id}.json"
    original_recommendation = recommendation_path.read_bytes()
    decided = Review.model_validate({
        **pending.model_dump(),
        "decision": decision,
        "reviewer": "Anslean",
        "review_date": datetime.now(UTC),
        "final_label": "duplicate" if decision == "approved" else "needs_info",
        "final_duplicated_enquiry_id": "ENQ-earlier" if decision == "approved" else None,
        "message": None if decision == "approved" else "The move-in date needs clarification.",
    })

    saved_path = writer.save_review(decided, tmp_path)

    # The review is saved at the same path as the pending review.
    assert saved_path == tmp_path / "reviews" / enquiry.enquiry_id / f"{result.run_id}.json"
    assert Review.model_validate_json(saved_path.read_text(encoding="utf-8")) == decided
    assert len(list((tmp_path / "reviews").rglob("*.json"))) == 1
    assert recommendation_path.read_bytes() == original_recommendation
    with pytest.raises(FileExistsError):
        writer.save_for_review(enquiry, result, tmp_path)
    assert Review.model_validate_json(saved_path.read_text(encoding="utf-8")) == decided


def test_mismatched_enquiry_rejected_before_saving(tmp_path, enquiry, result):
    enquiry.enquiry_id = "ENQ-other"

    with pytest.raises(ValueError, match="must refer to the enquiry"):
        writer.save_for_review(enquiry, result, tmp_path)

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("enquiry_id", ["../escape", "/absolute", "nested/id", "..", "a\\b", ""])
def test_enquiry_id_cannot_escape_output_directory(tmp_path, enquiry, enquiry_id):
    enquiry.enquiry_id = enquiry_id

    with pytest.raises(ValueError, match="enquiry_id must contain"):
        writer.save_enquiry(enquiry, tmp_path)

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("existing_file", [True, False])
def test_interrupted_write_never_publishes_incomplete_json(
    tmp_path, enquiry, monkeypatch, existing_file,
):
    saved_path = tmp_path / "enquiries" / f"{enquiry.enquiry_id}.json"
    original = None
    if existing_file:
        writer.save_enquiry(enquiry, tmp_path)
        original = saved_path.read_bytes()

    def interrupted_flush(fd):
        raise OSError("Interrupted save")

    monkeypatch.setattr(writer.os, "fsync", interrupted_flush)
    enquiry.message = "Updated message."
    with pytest.raises(OSError, match="Interrupted save"):
        writer.save_enquiry(enquiry, tmp_path)

    if existing_file:
        assert saved_path.read_bytes() == original
    else:
        assert not saved_path.exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_complete_replacement_is_in_same_directory(tmp_path, enquiry, monkeypatch):
    saved_path = writer.save_enquiry(enquiry, tmp_path)
    original = saved_path.read_bytes()
    real_replace = writer.os.replace
    enquiry.message = "Updated rental enquiry."

    def inspect_replace(source, destination):
        assert source.parent == destination.parent
        assert destination.read_bytes() == original
        assert Enquiry.model_validate_json(source.read_text(encoding="utf-8")) == enquiry
        real_replace(source, destination)

    monkeypatch.setattr(writer.os, "replace", inspect_replace)
    writer.save_enquiry(enquiry, tmp_path)

    assert Enquiry.model_validate_json(saved_path.read_text(encoding="utf-8")) == enquiry


def test_replace_failure_preserves_previous_review(tmp_path, enquiry, result, monkeypatch):
    pending = writer.save_for_review(enquiry, result, tmp_path)
    review_path = tmp_path / "reviews" / enquiry.enquiry_id / f"{result.run_id}.json"
    original = review_path.read_bytes()
    approved = Review.model_validate({
        **pending.model_dump(),
        "decision": "approved",
        "reviewer": "Anslean",
        "review_date": datetime.now(UTC),
        "final_label": "duplicate",
        "final_duplicated_enquiry_id": "ENQ-earlier",
    })

    def failed_replace(source, destination):
        raise OSError("Rename failed")

    monkeypatch.setattr(writer.os, "replace", failed_replace)
    with pytest.raises(OSError, match="Rename failed"):
        writer.save_review(approved, tmp_path)

    assert review_path.read_bytes() == original
    assert not list(tmp_path.rglob("*.tmp"))


def test_failed_recommendation_save_leaves_no_pending_review(
    tmp_path, enquiry, result, monkeypatch,
):
    real_replace = writer.os.replace

    def failed_recommendation_replace(source, destination):
        if destination.parent.name == "recommendations":
            raise OSError("Recommendation save failed")
        real_replace(source, destination)

    monkeypatch.setattr(writer.os, "replace", failed_recommendation_replace)
    with pytest.raises(OSError, match="Recommendation save failed"):
        writer.save_for_review(enquiry, result, tmp_path)

    # The recommendation save failed, so the review should not be saved.
    assert (tmp_path / "enquiries" / f"{enquiry.enquiry_id}.json").exists()
    assert not list((tmp_path / "reviews").rglob("*.json"))
    assert not list(tmp_path.rglob("*.tmp"))


def test_review_cannot_change_original_recommendation(tmp_path, enquiry, result):
    pending = writer.save_for_review(enquiry, result, tmp_path)
    pending.recommended_duplicated_enquiry_id = "ENQ-wrong"

    with pytest.raises(ValueError, match="saved recommendation"):
        writer.save_review(pending, tmp_path)


def test_mutated_invalid_review_is_not_written(tmp_path, enquiry, result):
    pending = writer.save_for_review(enquiry, result, tmp_path)
    pending.decision = "approved"

    with pytest.raises(ValidationError):
        writer.save_review(pending, tmp_path)

    review_path = tmp_path / "reviews" / enquiry.enquiry_id / f"{result.run_id}.json"
    assert Review.model_validate_json(review_path.read_text(encoding="utf-8")).decision == "pending"


def decided_review(pending, decision, reviewer="Anslean"):
    return Review.model_validate({
        **pending.model_dump(),
        "decision": decision,
        "reviewer": reviewer,
        "review_date": datetime.now(UTC),
        "final_label": "duplicate" if decision == "approved" else "needs_info",
        "final_duplicated_enquiry_id": "ENQ-earlier" if decision == "approved" else None,
        "message": None if decision == "approved" else "The move-in date needs clarification.",
    })


@pytest.mark.parametrize("first_decision", ["approved", "overridden"])
@pytest.mark.parametrize("second_decision", ["pending", "approved", "overridden", "identical"])
def test_decided_review_cannot_be_replaced(
    tmp_path, enquiry, result, first_decision, second_decision,
):
    pending = writer.save_for_review(enquiry, result, tmp_path)
    first = decided_review(pending, first_decision)
    saved_path = writer.save_review(first, tmp_path)
    original = saved_path.read_bytes()
    if second_decision == "pending":
        second = pending
    elif second_decision == "identical":
        second = first
    else:
        second = decided_review(pending, second_decision, reviewer="Another reviewer")

    with pytest.raises(writer.ReviewAlreadyDecidedError, match="cannot be replaced"):
        writer.save_review(second, tmp_path)

    assert saved_path.read_bytes() == original
    assert not list(tmp_path.rglob("*.tmp"))


@pytest.mark.parametrize("existing_review", [False, True])
def test_missing_recommendation_has_clear_error(tmp_path, enquiry, result, existing_review):
    pending = Review(
        enquiry_id=enquiry.enquiry_id,
        run_id=result.run_id,
        recommended_label="duplicate",
        recommended_duplicated_enquiry_id="ENQ-earlier",
        decision="pending",
    )
    recommendation_path = tmp_path / "recommendations" / f"{result.run_id}.json"
    review_path = tmp_path / "reviews" / enquiry.enquiry_id / f"{result.run_id}.json"
    original = None
    if existing_review:
        writer.save_for_review(enquiry, result, tmp_path)
        original = review_path.read_bytes()
        recommendation_path.unlink()

    with pytest.raises(writer.RecommendationNotFoundError) as caught:
        writer.save_review(decided_review(pending, "approved"), tmp_path)

    assert "recommendation not found" in str(caught.value)
    assert str(result.run_id) in str(caught.value)
    assert str(recommendation_path) in str(caught.value)
    assert isinstance(caught.value.__cause__, FileNotFoundError)
    if existing_review:
        assert review_path.read_bytes() == original
    else:
        assert not review_path.exists()

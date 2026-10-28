# Load saved review work without keyboard input or changes to runtime files.

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from core.manual_review import ReviewLoadError, find_pending_reviews, load_review_item
from core.writer import save_for_review, save_review
from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review
from models.review_item import ReviewItem
from models.triage_result import TriageResult


@pytest.fixture
def saved_item(tmp_path):
    """Make real output files using the same writer as the application."""
    def create(enquiry_id="ENQ-001", received_date="2026-10-28", run_id=None):
        enquiry = Enquiry(
            enquiry_id=enquiry_id,
            name="Amélie",
            email="amelie@example.com",
            message="I am looking for a studio in Montréal.",
            received_date=received_date,
        )
        recommendation = Recommendation(
            referred_enquiry_id=enquiry_id,
            label="duplicate",
            duplicated_enquiry_id="ENQ-earlier",
            reason="Matches an earlier enquiry.",
            evidence=[{
                "source": "message",
                "quote": "looking for a studio in Montréal",
                "support": "States rental intent.",
            }],
        )
        result = TriageResult(run_id or uuid4(), recommendation)
        review = save_for_review(enquiry, result, tmp_path)
        return ReviewItem(review, enquiry, recommendation)

    return create


def review_path(output_dir, item):
    return output_dir / "reviews" / item.review.enquiry_id / f"{item.review.run_id}.json"


def test_find_pending_returns_items_and_warns_about_broken_files(tmp_path, saved_item):
    later = saved_item("ENQ-later", "2026-10-28")
    earlier = saved_item("ENQ-earlier-pending", "2026-10-01")
    broken = saved_item("ENQ-broken")
    broken_path = review_path(tmp_path, broken)
    broken_path.write_text("{broken JSON", encoding="utf-8")
    # These are not reviews and must not be read.
    broken_path.with_suffix(".lock").write_text("not JSON", encoding="utf-8")
    broken_path.with_suffix(".tmp").write_text("not JSON", encoding="utf-8")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    items, warnings = find_pending_reviews(tmp_path)

    assert items == [earlier, later]
    assert len(warnings) == 1
    assert str(broken_path) in warnings[0]
    assert "Invalid review JSON or model data" in warnings[0]
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


def test_load_review_item_returns_all_three_complete_models(tmp_path, saved_item):
    expected = saved_item()

    actual = load_review_item(review_path(tmp_path, expected), tmp_path)

    assert actual == expected
    assert actual.enquiry.name == "Amélie"
    assert actual.enquiry.email == "amelie@example.com"
    assert actual.recommendation.evidence == expected.recommendation.evidence


def item_file(output_dir, item, kind):
    if kind == "review":
        return review_path(output_dir, item)
    if kind == "enquiry":
        return output_dir / "enquiries" / f"{item.review.enquiry_id}.json"
    return output_dir / "recommendations" / f"{item.review.run_id}.json"


@pytest.mark.parametrize("kind", ["review", "enquiry", "recommendation"])
def test_load_missing_file_has_clear_error(tmp_path, saved_item, kind):
    item = saved_item()
    missing_path = item_file(tmp_path, item, kind)
    missing_path.unlink()

    with pytest.raises(ReviewLoadError, match=f"{kind} file missing") as caught:
        load_review_item(review_path(tmp_path, item), tmp_path)

    assert str(missing_path) in str(caught.value)


@pytest.mark.parametrize("kind", ["review", "enquiry", "recommendation"])
@pytest.mark.parametrize("contents", [b"{broken JSON", b"{}", b"\xff"])
def test_load_corrupt_file_has_clear_error(tmp_path, saved_item, kind, contents):
    item = saved_item()
    corrupt_path = item_file(tmp_path, item, kind)
    corrupt_path.write_bytes(contents)

    with pytest.raises(ReviewLoadError, match=f"Invalid {kind}") as caught:
        load_review_item(review_path(tmp_path, item), tmp_path)

    assert str(corrupt_path) in str(caught.value)


@pytest.mark.parametrize(("kind", "changes", "message"), [
    ("review", {"enquiry_id": "../outside"}, "Review path does not match"),
    ("review", {"run_id": str(UUID(int=99))}, "Review path does not match"),
    ("enquiry", {"enquiry_id": "ENQ-other"}, "Enquiry ID does not match"),
    ("recommendation", {"referred_enquiry_id": "ENQ-other"}, "Recommendation enquiry ID does not match"),
    ("review", {"recommended_label": "genuine", "recommended_duplicated_enquiry_id": None}, "Recommended outcome does not match"),
    ("recommendation", {"duplicated_enquiry_id": "ENQ-different"}, "Recommended outcome does not match"),
])
def test_load_rejects_mismatched_links(tmp_path, saved_item, kind, changes, message):
    item = saved_item()
    changed_path = item_file(tmp_path, item, kind)
    contents = json.loads(changed_path.read_text(encoding="utf-8"))
    changed_path.write_text(json.dumps({**contents, **changes}), encoding="utf-8")

    with pytest.raises(ReviewLoadError, match=message):
        load_review_item(review_path(tmp_path, item), tmp_path)


@pytest.mark.parametrize("missing_kind", ["enquiry", "recommendation"])
def test_find_pending_skips_incomplete_item_with_warning(tmp_path, saved_item, missing_kind):
    valid = saved_item("ENQ-valid")
    broken = saved_item("ENQ-broken")
    missing_path = item_file(tmp_path, broken, missing_kind)
    missing_path.unlink()

    items, warnings = find_pending_reviews(tmp_path)

    assert items == [valid]
    assert len(warnings) == 1
    assert str(review_path(tmp_path, broken)) in warnings[0]
    assert f"{missing_kind} file missing: {missing_path}" in warnings[0]


@pytest.mark.parametrize("decision", ["approved", "overridden"])
def test_find_pending_excludes_decided_reviews_without_loading_their_bodies(
    tmp_path, saved_item, decision,
):
    item = saved_item()
    decided = Review.model_validate({
        **item.review.model_dump(),
        "decision": decision,
        "reviewer": "Anslean",
        "review_date": datetime.now(UTC),
        "final_label": "duplicate" if decision == "approved" else "needs_info",
        "final_duplicated_enquiry_id": "ENQ-earlier" if decision == "approved" else None,
        "message": None if decision == "approved" else "Move-in date needs clarification.",
    })
    save_review(decided, tmp_path)
    item_file(tmp_path, item, "enquiry").unlink()
    item_file(tmp_path, item, "recommendation").unlink()

    assert find_pending_reviews(tmp_path) == ([], [])


def test_find_pending_sorts_by_date_then_enquiry_and_run(tmp_path, saved_item):
    missing = saved_item("ENQ-missing", None, UUID(int=6))
    last_date = saved_item("ENQ-last-date", "9999-12-31", UUID(int=5))
    later = saved_item("ENQ-later", "2026-10-28", UUID(int=4))
    tie_b = saved_item("ENQ-B", "2026-10-01", UUID(int=3))
    tie_a_run_2 = saved_item("ENQ-A", "2026-10-01", UUID(int=2))
    tie_a_run_1 = saved_item("ENQ-A", "2026-10-01", UUID(int=1))

    items, warnings = find_pending_reviews(tmp_path)

    assert items == [tie_a_run_1, tie_a_run_2, tie_b, later, last_date, missing]
    assert warnings == []


@pytest.mark.parametrize("received_date", ["yesterday", "2026-02-30", ""])
def test_find_pending_skips_invalid_dates_with_warning(tmp_path, saved_item, received_date):
    item = saved_item(received_date=received_date)

    items, warnings = find_pending_reviews(tmp_path)

    assert items == []
    assert len(warnings) == 1
    assert "Invalid enquiry received_date" in warnings[0]
    assert str(review_path(tmp_path, item)) in warnings[0]


def test_find_pending_with_no_output_returns_empty_without_creating_folders(tmp_path):
    output_dir = tmp_path / "not-created"

    assert find_pending_reviews(output_dir) == ([], [])
    assert not output_dir.exists()

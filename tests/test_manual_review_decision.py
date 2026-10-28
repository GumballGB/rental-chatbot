# Scripted answers exercise human decisions without keyboard input.

from datetime import UTC, datetime
from uuid import UUID

import pytest

from core.manual_review import ask_for_decision
from core.manual_review import manual_review as run_manual_review
from core.writer import save_for_review
from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review
from models.review_item import ReviewItem
from models.triage_result import TriageResult


@pytest.fixture
def make_item():
    def create(label="genuine", duplicate_id=None):
        enquiry = Enquiry(enquiry_id="ENQ-001", message="I am looking for a studio.")
        recommendation = Recommendation(
            referred_enquiry_id=enquiry.enquiry_id,
            label=label,
            duplicated_enquiry_id=duplicate_id,
            reason="Rental enquiry classification.",
            evidence=[{
                "source": "message",
                "quote": "looking for a studio",
                "support": "Shows rental intent.",
            }],
        )
        review = Review(
            enquiry_id=enquiry.enquiry_id,
            run_id=UUID(int=1),
            recommended_label=label,
            recommended_duplicated_enquiry_id=duplicate_id,
            decision="pending",
        )
        return ReviewItem(review, enquiry, recommendation)

    return create


def scripted_ask(answers):
    """Return a replacement for input plus the prompts it received."""
    answers = iter(answers)
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return next(answers)

    return ask, prompts


@pytest.mark.parametrize(("label", "duplicate_id"), [
    ("genuine", None), ("needs_info", None), ("spam", None), ("duplicate", "ENQ-earlier"),
])
def test_approve_preserves_complete_recommended_outcome(make_item, label, duplicate_id):
    item = make_item(label, duplicate_id)
    ask, prompts = scripted_ask([" A ", ""])
    shown = []
    before = datetime.now(UTC)

    decided = ask_for_decision(item, "Anslean", ask=ask, show=shown.append)

    assert isinstance(decided, Review)
    assert decided.decision == "approved"
    assert decided.enquiry_id == item.review.enquiry_id
    assert decided.run_id == item.review.run_id
    assert decided.recommended_label == label
    assert decided.recommended_duplicated_enquiry_id == duplicate_id
    assert decided.final_label == label
    assert decided.final_duplicated_enquiry_id == duplicate_id
    assert decided.reviewer == "Anslean"
    assert before <= decided.review_date <= datetime.now(UTC)
    assert decided.review_date.tzinfo is UTC
    assert decided.message is None
    assert item.review.decision == "pending"
    assert len(prompts) == 2
    assert shown == []


@pytest.mark.parametrize(("answer", "expected"), [
    ("", None), (" \t ", None), ("  Contact details checked.  ", "Contact details checked."),
])
def test_approve_comment_is_optional(make_item, answer, expected):
    ask, _ = scripted_ask(["a", answer])

    decided = ask_for_decision(make_item(), "Anslean", ask=ask, show=lambda text: None)

    assert decided.message == expected


@pytest.mark.parametrize(("initial_label", "initial_duplicate", "answers", "label", "duplicate_id"), [
    ("genuine", None, ["o", " NEEDS_INFO ", "  Move-in date is missing.  "], "needs_info", None),
    ("genuine", None, ["o", "spam", "Unrelated marketing."], "spam", None),
    ("genuine", None, ["o", "duplicate", " ENQ-earlier ", "Matches an earlier enquiry."], "duplicate", "ENQ-earlier"),
    ("duplicate", "ENQ-earlier", ["o", "genuine", "This is a separate request."], "genuine", None),
    ("duplicate", "ENQ-earlier", ["o", "duplicate", "ENQ-other", "The original duplicate ID was wrong."], "duplicate", "ENQ-other"),
])
def test_override_records_validated_outcome_and_explanation(
    make_item, initial_label, initial_duplicate, answers, label, duplicate_id,
):
    item = make_item(initial_label, initial_duplicate)
    ask, prompts = scripted_ask(answers)
    shown = []

    decided = ask_for_decision(item, "Anslean", ask=ask, show=shown.append)

    assert isinstance(decided, Review)
    assert decided.decision == "overridden"
    assert decided.enquiry_id == item.review.enquiry_id
    assert decided.run_id == item.review.run_id
    assert decided.recommended_label == initial_label
    assert decided.recommended_duplicated_enquiry_id == initial_duplicate
    assert decided.final_label == label
    assert decided.final_duplicated_enquiry_id == duplicate_id
    assert decided.message == answers[-1].strip()
    assert decided.reviewer == "Anslean"
    assert decided.review_date.tzinfo is UTC
    assert all(choice in prompts[1] for choice in ["genuine", "needs_info", "spam", "duplicate"])
    assert len(prompts) == (4 if label == "duplicate" else 3)
    assert shown == []


def test_unrecognised_menu_answers_reask(make_item):
    ask, prompts = scripted_ask(["yes", "?", "", "a", ""])
    shown = []

    decided = ask_for_decision(make_item(), "Anslean", ask=ask, show=shown.append)

    assert decided.decision == "approved"
    assert len(shown) == 3
    assert all("Choose a, o, s, or q" in message for message in shown)
    assert len(prompts) == 5


@pytest.mark.parametrize(("invalid_answers", "error_text"), [
    (["invalid_label", "A reason."], "Input should be"),
    (["duplicate", "  ", "A reason."], "final_duplicated_enquiry_id is required"),
    (["duplicate", "ENQ-001", "A reason."], "cannot be a duplicate of itself"),
    (["needs_info", " \t "], "message is required"),
    (["genuine", "A reason."], "must differ from recommended outcome"),
])
def test_invalid_override_shows_validation_error_and_reasks(make_item, invalid_answers, error_text):
    ask, prompts = scripted_ask(["o", *invalid_answers, "needs_info", "Clarify move-in date."])
    shown = []

    decided = ask_for_decision(make_item(), "Anslean", ask=ask, show=shown.append)

    assert decided.decision == "overridden"
    assert decided.final_label == "needs_info"
    assert decided.message == "Clarify move-in date."
    assert len(shown) == 1
    assert error_text in shown[0]
    assert len(prompts) == 1 + len(invalid_answers) + 2


@pytest.mark.parametrize(("answer", "expected"), [
    ("s", "skip"), (" S ", "skip"), ("q", "quit"), (" Q ", "quit"),
])
def test_skip_and_quit_are_distinct_and_require_no_more_input(make_item, answer, expected):
    item = make_item()
    ask, prompts = scripted_ask([answer])

    assert ask_for_decision(item, "Anslean", ask=ask, show=lambda text: None) == expected
    assert len(prompts) == 1
    assert item.review.decision == "pending"


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
@pytest.mark.parametrize("prefix", [
    [], ["a"], ["o"], ["o", "duplicate"], ["o", "duplicate", "ENQ-earlier"],
])
def test_interruption_at_any_prompt_returns_quit(make_item, interruption, prefix):
    item = make_item()
    answers = iter(prefix)

    def ask(prompt):
        try:
            return next(answers)
        except StopIteration:
            raise interruption from None

    assert ask_for_decision(item, "Anslean", ask=ask, show=lambda text: None) == "quit"
    assert item.review.decision == "pending"


def test_collecting_a_decision_does_not_write_or_modify_the_item(tmp_path, make_item):
    item = make_item()
    save_for_review(item.enquiry, TriageResult(item.review.run_id, item.recommendation), tmp_path)
    files_before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    models_before = (item.review.model_dump(), item.enquiry.model_dump(), item.recommendation.model_dump())
    ask, _ = scripted_ask(["a", ""])

    decided = ask_for_decision(item, "Anslean", ask=ask, show=lambda text: None)

    assert decided.decision == "approved"
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.json")} == files_before
    assert (item.review.model_dump(), item.enquiry.model_dump(), item.recommendation.model_dump()) == models_before


@pytest.mark.parametrize("decision", ["approved", "overridden"])
def test_manual_review_saves_a_decided_review_to_the_output_directory(
    tmp_path, make_item, monkeypatch, decision,
):
    item = make_item()
    save_for_review(item.enquiry, TriageResult(item.review.run_id, item.recommendation), tmp_path)
    decided = Review.model_validate({
        **item.review.model_dump(),
        "decision": decision,
        "reviewer": "Anslean",
        "review_date": datetime.now(UTC),
        "final_label": "genuine" if decision == "approved" else "needs_info",
        "message": None if decision == "approved" else "Clarify move-in date.",
    })
    monkeypatch.setattr("core.manual_review.DEFAULT_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("core.manual_review.find_pending_reviews", lambda: ([item], []))
    monkeypatch.setattr("core.manual_review.ask_for_decision", lambda *args, **kwargs: decided)
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)

    run_manual_review()

    path = tmp_path / "reviews" / item.review.enquiry_id / f"{item.review.run_id}.json"
    assert Review.model_validate_json(path.read_text(encoding="utf-8")) == decided

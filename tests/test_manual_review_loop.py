# Drive a complete review session against temporary runtime files.

import runpy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from core.manual_review import manual_review, run_manual_review
from core.writer import save_for_review, save_review
from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review
from models.triage_result import TriageResult


@pytest.fixture
def make_pending(tmp_path):
    def create(enquiry_id, received_date="2026-10-28"):
        enquiry = Enquiry(
            enquiry_id=enquiry_id,
            message="I am looking for a studio.",
            received_date=received_date,
        )
        recommendation = Recommendation(
            referred_enquiry_id=enquiry_id,
            label="genuine",
            reason="Clear rental intent.",
            evidence=[{
                "source": "message",
                "quote": "looking for a studio",
                "support": "States a rental request.",
            }],
        )
        return save_for_review(enquiry, TriageResult(uuid4(), recommendation), tmp_path)

    return create


def review_path(output_dir, review):
    return output_dir / "reviews" / review.enquiry_id / f"{review.run_id}.json"


def load_saved_review(output_dir, review):
    return Review.model_validate_json(review_path(output_dir, review).read_text(encoding="utf-8"))


def test_loop_saves_decisions_skips_without_changes_and_shows_each_item_once(
    tmp_path, make_pending, monkeypatch,
):
    skipped = make_pending("ENQ-003", "2026-10-03")
    overridden = make_pending("ENQ-002", "2026-10-02")
    approved = make_pending("ENQ-001", "2026-10-01")
    skipped_before = review_path(tmp_path, skipped).read_bytes()
    bodies_before = {
        path: path.read_bytes()
        for kind in ["enquiries", "recommendations"]
        for path in (tmp_path / kind).glob("*.json")
    }
    answers = iter(["a", "", "o", "needs_info", "Clarify the move-in date.", "s"])
    shown = []

    def unexpected_print(*args, **kwargs):
        pytest.fail("Every message must go through the injected show function.")

    monkeypatch.setattr("builtins.print", unexpected_print)

    counts = run_manual_review(
        output_dir=tmp_path, reviewer="Test Reviewer",
        ask=lambda prompt: next(answers), show=shown.append,
    )

    assert counts == {"approved": 1, "overridden": 1, "skipped": 1, "warned": 0}
    assert load_saved_review(tmp_path, approved).decision == "approved"
    assert load_saved_review(tmp_path, approved).reviewer == "Test Reviewer"
    changed = load_saved_review(tmp_path, overridden)
    assert changed.decision == "overridden"
    assert changed.final_label == "needs_info"
    assert changed.message == "Clarify the move-in date."
    assert changed.reviewer == "Test Reviewer"
    assert review_path(tmp_path, skipped).read_bytes() == skipped_before
    assert all(path.read_bytes() == contents for path, contents in bodies_before.items())
    text = "\n".join(shown)
    for position in range(1, 4):
        assert text.count(f"Review {position} of 3") == 1
    assert "Pending reviews:" not in text


def test_loop_displays_discovery_warnings_through_show(tmp_path, make_pending):
    valid = make_pending("ENQ-valid")
    corrupt = make_pending("ENQ-corrupt")
    missing = make_pending("ENQ-missing")
    corrupt_path = review_path(tmp_path, corrupt)
    corrupt_path.write_text("{broken JSON", encoding="utf-8")
    missing_path = tmp_path / "recommendations" / f"{missing.run_id}.json"
    missing_path.unlink()
    shown = []

    counts = run_manual_review(tmp_path, ask=lambda prompt: "s", show=shown.append)

    assert counts == {"approved": 0, "overridden": 0, "skipped": 1, "warned": 2}
    assert any(str(corrupt_path) in message for message in shown)
    assert any(str(missing_path) in message for message in shown)
    assert load_saved_review(tmp_path, valid).decision == "pending"
    assert corrupt_path.read_text(encoding="utf-8") == "{broken JSON"


def test_quit_keeps_current_and_unvisited_reviews_unchanged(tmp_path, make_pending):
    first = make_pending("ENQ-001")
    current = make_pending("ENQ-002")
    unvisited = make_pending("ENQ-003")
    untouched = {review_path(tmp_path, review): review_path(tmp_path, review).read_bytes()
                 for review in [current, unvisited]}
    answers = iter(["a", "", "q"])
    shown = []

    counts = run_manual_review(tmp_path, ask=lambda prompt: next(answers), show=shown.append)

    assert counts == {"approved": 1, "overridden": 0, "skipped": 0, "warned": 0}
    assert load_saved_review(tmp_path, first).decision == "approved"
    assert load_saved_review(tmp_path, first).reviewer == "admin"
    assert all(path.read_bytes() == contents for path, contents in untouched.items())
    assert "Review 3 of 3" not in "\n".join(shown)


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
def test_interrupted_decision_leaves_pending_files_unchanged(tmp_path, make_pending, interruption):
    make_pending("ENQ-001")
    make_pending("ENQ-002")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    answers = iter(["a"])

    def ask(prompt):
        try:
            return next(answers)
        except StopIteration:
            raise interruption from None

    counts = run_manual_review(tmp_path, ask=ask, show=lambda text: None)

    assert counts == {"approved": 0, "overridden": 0, "skipped": 0, "warned": 0}
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.json")} == before


def test_already_decided_item_is_reported_and_the_loop_continues(tmp_path, make_pending):
    first = make_pending("ENQ-001")
    second = make_pending("ENQ-002")
    existing_decision = Review.model_validate({
        **first.model_dump(),
        "decision": "approved",
        "final_label": "genuine",
        "reviewer": "Earlier Reviewer",
        "review_date": datetime.now(UTC),
    })
    answers = iter(["a", "", "a", ""])
    shown = []
    original = []

    def ask(prompt):
        # Simulate an item that was decided after discovery, with no threads.
        if not original:
            save_review(existing_decision, tmp_path)
            original.append(review_path(tmp_path, first).read_bytes())
        return next(answers)

    counts = run_manual_review(tmp_path, reviewer="Test Reviewer", ask=ask, show=shown.append)

    assert counts == {"approved": 1, "overridden": 0, "skipped": 1, "warned": 1}
    assert review_path(tmp_path, first).read_bytes() == original[0]
    assert load_saved_review(tmp_path, second).reviewer == "Test Reviewer"
    assert any(str(review_path(tmp_path, first)) in message and "already approved" in message
               for message in shown)


def test_other_saving_errors_propagate_without_claiming_success(tmp_path, make_pending, monkeypatch):
    pending = make_pending("ENQ-001")
    before = review_path(tmp_path, pending).read_bytes()
    answers = iter(["a", ""])
    shown = []

    def failed_save(*args, **kwargs):
        raise OSError("Disk full")

    monkeypatch.setattr("core.manual_review.save_review", failed_save)
    with pytest.raises(OSError, match="Disk full"):
        run_manual_review(tmp_path, ask=lambda prompt: next(answers), show=shown.append)

    assert review_path(tmp_path, pending).read_bytes() == before
    assert not any("Saved decision" in message for message in shown)


def test_empty_loop_does_not_prompt_or_create_output(tmp_path):
    output_dir = tmp_path / "not-created"
    shown = []

    def unexpected_ask(prompt):
        pytest.fail("An empty worklist must not ask for a decision.")

    counts = run_manual_review(output_dir, ask=unexpected_ask, show=shown.append)

    assert counts == {"approved": 0, "overridden": 0, "skipped": 0, "warned": 0}
    assert any("Found 0 pending reviews" in message for message in shown)
    assert not output_dir.exists()


@pytest.mark.parametrize(("answer", "reviewer"), [("", "admin"), ("  ", "admin"), (" Pat ", "Pat")])
def test_entry_point_passes_reviewer_name_to_loop(monkeypatch, answer, reviewer):
    counts = {"approved": 0, "overridden": 0, "skipped": 0, "warned": 0}
    passed = []
    monkeypatch.setattr("builtins.input", lambda prompt: answer)

    def fake_loop(**kwargs):
        passed.append(kwargs)
        return counts

    monkeypatch.setattr("core.manual_review.run_manual_review", fake_loop)

    assert manual_review() == counts
    assert passed == [{"reviewer": reviewer}]


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
def test_entry_point_can_cancel_before_starting_the_loop(monkeypatch, interruption):
    def interrupted_input(prompt):
        raise interruption

    def unexpected_loop(**kwargs):
        pytest.fail("Cancelling the name prompt must not start a session.")

    monkeypatch.setattr("builtins.input", interrupted_input)
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("core.manual_review.run_manual_review", unexpected_loop)

    assert manual_review() is None


def test_script_entry_point_starts_a_session(tmp_path, monkeypatch):
    output_dir = tmp_path / "not-created"
    shown = []
    monkeypatch.setattr("core.writer.DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr("builtins.input", lambda prompt: "Test Reviewer")
    monkeypatch.setattr("builtins.print", shown.append)
    script = Path(__file__).resolve().parents[1] / "core" / "manual_review.py"

    runpy.run_path(str(script), run_name="__main__")

    assert any("Found 0 pending reviews" in message for message in shown)
    assert not output_dir.exists()

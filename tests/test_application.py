# Exercise the chatbot-to-triage-to-human handoffs with real runtime files.

import json
from uuid import UUID

import pytest

from core.audit import read_events
from core.manual_review import find_pending_reviews
from core.store import JsonStore
from main import main, run_application
from models.enquiry import Enquiry
from models.review import Review
from tests.fakes import FakeAnthropicClient, text_response, tool_use_response

ENQUIRY_ID = f"ENQ-{UUID(int=1)}"


def make_client(monkeypatch, *, quote="Looking for a rental.", stop_reason="end_turn"):
    monkeypatch.setattr("agents.anthropic_functions.uuid.uuid4", lambda: UUID(int=1))
    extraction = {
        "name": "Sam", "email": "sam@example.com", "phone": None,
        "move_in_date": None, "budget": 1900, "listing_id": "LST-002",
        "message": "Looking for a rental.", "declined_fields": ["phone"],
    }
    recommendation = {
        "referred_enquiry_id": ENQUIRY_ID, "label": "genuine",
        "reason": "Rental request with a name and contact.",
        "evidence": [{"source": "message", "quote": quote, "support": "Rental intent."}],
    }
    return FakeAnthropicClient([
        text_response("Thanks, Sam."),
        text_response(json.dumps(extraction)),
        tool_use_response("find_duplicate_enquiry_candidates", {}),
        text_response(json.dumps(recommendation), stop_reason=stop_reason),
    ])


@pytest.mark.parametrize(("decisions", "decision", "final_label"), [
    (["a", ""], "approved", "genuine"),
    (["o", "needs_info", "Contact needs clarification."], "overridden", "needs_info"),
    (["s"], "pending", None),
    (["q"], "pending", None),
])
def test_chat_through_human_decision(monkeypatch, tmp_path, decisions, decision, final_label):
    client = make_client(monkeypatch)
    answers = iter(["I'm Sam, sam@example.com. Looking for a rental.", "done", "Pat", *decisions])

    def ask(prompt):
        if prompt.startswith("Reviewer name"):
            pending, warnings = find_pending_reviews(tmp_path / "output")
            assert not warnings
            assert len(pending) == 1
            assert pending[0].review.final_label is None
        return next(answers)

    monkeypatch.setattr("builtins.input", ask)
    result = run_application(
        client, JsonStore(), output_dir=tmp_path / "output", audit_dir=tmp_path / "audit",
    )

    output = tmp_path / "output"
    saved = Review.model_validate_json(
        (output / "reviews" / ENQUIRY_ID / f"{result.run_id}.json").read_text()
    )
    assert saved.decision == decision
    assert saved.final_label == final_label
    assert saved.reviewer == ("Pat" if decision != "pending" else None)
    enquiry = Enquiry.model_validate_json((output / "enquiries" / f"{ENQUIRY_ID}.json").read_text())
    assert enquiry.email == "sam@example.com"
    assert enquiry.budget_currency == "CAD"
    events = read_events(tmp_path / "audit" / f"{result.run_id}.jsonl")
    assert events[-1].run_succeeded is True
    triage_request = json.dumps(client.messages.calls[2])
    assert "sam@example.com" not in triage_request
    assert "has_contact" in triage_request
    assert len(client.messages.calls) == 4


def test_queue_only_leaves_discoverable_pending_review(monkeypatch, tmp_path, capsys):
    client = make_client(monkeypatch)
    answers = iter(["Looking for a rental.", "done"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    result = run_application(client, JsonStore(), output_dir=tmp_path, audit_dir=tmp_path / "audit", review=False)

    items, warnings = find_pending_reviews(tmp_path)
    assert not warnings
    assert [item.review.run_id for item in items] == [result.run_id]
    assert items[0].review.decision == "pending"
    assert "python -m core.manual_review" in capsys.readouterr().out


@pytest.mark.parametrize(("kwargs", "error"), [
    ({"quote": "Invented evidence"}, ValueError),
    ({"stop_reason": "max_tokens"}, RuntimeError),
])
def test_triage_failure_keeps_enquiry_without_opening_review(monkeypatch, tmp_path, capsys, kwargs, error):
    client = make_client(monkeypatch, **kwargs)
    answers = iter(["Looking for a rental.", "done"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    with pytest.raises(error):
        run_application(client, JsonStore(), output_dir=tmp_path, audit_dir=tmp_path / "audit")

    assert (tmp_path / "enquiries" / f"{ENQUIRY_ID}.json").is_file()
    assert find_pending_reviews(tmp_path) == ([], [])
    assert not (tmp_path / "recommendations").exists()
    events = read_events(next((tmp_path / "audit").glob("*.jsonl")))
    assert events[-1].run_succeeded is False
    assert f"Triage failed for {ENQUIRY_ID}" in capsys.readouterr().out


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
def test_cancel_reviewer_prompt_preserves_pending_review(monkeypatch, tmp_path, interruption):
    client = make_client(monkeypatch)
    answers = iter(["Looking for a rental.", "done"])

    def ask(prompt):
        if prompt.startswith("Reviewer name"):
            raise interruption
        return next(answers)

    monkeypatch.setattr("builtins.input", ask)
    result = run_application(client, JsonStore(), output_dir=tmp_path, audit_dir=tmp_path / "audit")

    items, warnings = find_pending_reviews(tmp_path)
    assert not warnings
    assert [item.review.run_id for item in items] == [result.run_id]


def test_empty_chat_does_not_triage_or_create_review(monkeypatch, tmp_path):
    client = FakeAnthropicClient([])
    monkeypatch.setattr("builtins.input", lambda prompt: "done")

    with pytest.raises(RuntimeError, match="empty conversation"):
        run_application(client, JsonStore(), output_dir=tmp_path, audit_dir=tmp_path / "audit")

    assert not client.messages.calls
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(("argv", "review"), [([], True), (["--queue-only"], False)])
def test_cli_wires_review_mode(monkeypatch, argv, review):
    client, store = object(), object()
    calls = []
    monkeypatch.setattr("main.boot_anthropic", lambda: client)
    monkeypatch.setattr("main.JsonStore", lambda: store)
    monkeypatch.setattr("main.dotenv.load_dotenv", lambda: None)
    monkeypatch.setattr("main.run_application", lambda *args, **kwargs: calls.append((args, kwargs)))

    main(argv)

    assert calls == [((client, store), {"review": review})]

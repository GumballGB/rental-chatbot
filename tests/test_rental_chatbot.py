import json

from agents.rental_chatbot import run_rental_chat
from core.store import JsonStore
from tests.fakes import FakeAnthropicClient, text_response


def test_run_rental_chat_uses_moved_workflow(monkeypatch):
    extracted_data = {
        "name": "Sam",
        "email": "sam@example.com",
        "phone": None,
        "move_in_date": None,
        "budget": 1900,
        "message": "Looking for a rental.",
        "listing_id": "LST-002",
        "declined_fields": ["phone"],
    }
    client = FakeAnthropicClient(
        [
            text_response("Thanks, Sam."),
            text_response(json.dumps(extracted_data)),
        ]
    )
    answers = iter(["I'm Sam with a budget of 1900.", "done"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    enquiry, declined_fields = run_rental_chat(client, JsonStore())

    assert enquiry.name == "Sam"
    assert enquiry.listing_id == "LST-002"
    assert enquiry.budget_currency == "CAD"
    assert declined_fields == {"phone"}

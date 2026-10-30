# Application-owned duplicate matching stays private throughout tool turns.

import json

import pytest

from agents.agent_triage import triage_enquiry
from core.audit import read_events
from core.store import JsonStore
from core.tools import FIND_DUPLICATE_ENQUIRY_CANDIDATES_SCHEMA
from models.enquiry import Enquiry
from tests.fakes import FakeAnthropicClient, text_response, tool_use_response


@pytest.mark.parametrize("match_field", ["email", "phone", "name"])
def test_duplicate_lookup_uses_bound_contacts_and_filters_every_tool_turn(
    tmp_path, monkeypatch, match_field,
):
    current = Enquiry(
        enquiry_id="ENQ-current",
        name="Amélie Tremblay",
        email="amelie.private@example.com",
        phone="+1 514 555 0123",
        received_date="2026-10-29",
        listing_id="LST-001",
        move_in_date="2026-12-01",
        message="Amélie here. Email amelie.private@example.com or call +1 514 555 0123.",
    )
    history = Enquiry(
        enquiry_id="ENQ-history",
        name=current.name if match_field == "name" else "Sofie Andersen",
        email=current.email if match_field == "email" else "sofie.private@example.com",
        phone=current.phone if match_field == "phone" else "+45 20 30 40 50",
        received_date="2026-10-20",
        listing_id=current.listing_id,
        move_in_date=current.move_in_date,
    )
    history.message = f"{history.name} here. Contact {history.email} or {history.phone}."
    store = JsonStore()
    # The chatbot-created enquiry is deliberately absent from the read-only store.
    store.enquiries = {history.enquiry_id: history}
    originals = (current.model_dump(), history.model_dump())
    matching_calls = []
    real_find = store.find_duplicate_enquiry_candidates

    def record_matching_arguments(**kwargs):
        matching_calls.append(kwargs)
        return real_find(**kwargs)

    monkeypatch.setattr(store, "find_duplicate_enquiry_candidates", record_matching_arguments)
    recommendation = {
        "referred_enquiry_id": current.enquiry_id,
        "duplicated_enquiry_id": history.enquiry_id,
        "label": "duplicate",
        "reason": "The application found a matching historical enquiry.",
        "evidence": [{
            "source": "tool_result",
            "quote": f'"matched_on": ["{match_field}"',
            "support": "The local duplicate check reports a matching field.",
        }],
    }
    client = FakeAnthropicClient([
        tool_use_response("find_duplicate_enquiry_candidates", {}, tool_use_id="duplicates"),
        tool_use_response("get_enquiry", {"enquiry_id": history.enquiry_id}, tool_use_id="history"),
        text_response(json.dumps(recommendation)),
    ])

    result = triage_enquiry(
        current, client, store, audit_dir=tmp_path / "audit", output_dir=tmp_path / "output",
    )

    assert result.recommendation.label == "duplicate"
    assert matching_calls == [{
        "exclude_enquiry_id": current.enquiry_id,
        "received_before": current.received_date,
        "email": current.email,
        "phone": current.phone,
        "name": current.name,
        "listing_id": current.listing_id,
        "move_in_date": current.move_in_date,
    }]
    assert len(client.messages.calls) == 3
    requests = json.dumps(client.messages.calls, ensure_ascii=False, default=vars)
    private_values = {
        current.name, current.email, current.phone,
        history.name, history.email, history.phone,
    }
    for value in private_values:
        assert value not in requests

    candidates = json.loads(client.messages.calls[1]["messages"][-1]["content"][0]["content"])
    assert candidates["count"] == 1
    candidate = candidates["candidates"][0]
    assert candidate["enquiry_id"] == history.enquiry_id
    assert match_field in candidate["matched_on"]
    retrieved = json.loads(client.messages.calls[2]["messages"][-1]["content"][0]["content"])
    for view in (candidate, retrieved):
        assert {"name", "email", "phone"}.isdisjoint(view)
        assert view["has_name"] is True
        assert view["has_contact"] is True
        assert "[NAME]" in view["message"]
        assert "[EMAIL]" in view["message"]
        assert "[PHONE]" in view["message"]

    audit_path = tmp_path / "audit" / f"{result.run_id}.jsonl"
    audit_text = audit_path.read_text(encoding="utf-8")
    for value in private_values:
        assert value not in audit_text
    events = read_events(audit_path)
    call = next(event for event in events if event.type == "tool_call"
                and event.tool == "find_duplicate_enquiry_candidates")
    assert {"name", "email", "phone"}.isdisjoint(call.args)
    assert call.args["exclude_enquiry_id"] == current.enquiry_id
    assert (current.model_dump(), history.model_dump()) == originals
    saved = Enquiry.model_validate_json(
        (tmp_path / "output" / "enquiries" / f"{current.enquiry_id}.json").read_text(encoding="utf-8")
    )
    assert saved == current


def test_duplicate_schema_requires_no_model_supplied_search_values():
    schema = FIND_DUPLICATE_ENQUIRY_CANDIDATES_SCHEMA["input_schema"]

    assert schema["properties"] == {}
    assert schema["additionalProperties"] is False

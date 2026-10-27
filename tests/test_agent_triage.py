# Tests for the agent_triage module, specifically the triage_enquiry function.

import json

import pytest

from agents.agent_triage import triage_enquiry
from core.audit import read_events
from core.store import JsonStore
from models.enquiry import Enquiry
from tests.fakes import FakeAnthropicClient, text_response


def make_enquiry():
    return Enquiry(
        enquiry_id="ENQ-001",
        name="Sam",
        email="sam@example.com",
        budget=1900,
        budget_currency="CAD",
        message="I am looking for a studio in Griffintown.",
        listing_id="LST-001",
    )


def test_triage_writes_events_as_they_happen(tmp_path):
    recommendation_data = {
        "referred_enquiry_id": "ENQ-001",
        "duplicated_enquiry_id": None,
        "label": "genuine",
        "reason": "The enquiry contains clear rental intent.",
        "evidence": [
            {
                "source": "message",
                "quote": "looking for a studio in Griffintown",
                "support": "Provides a concrete rental request.",
            }
        ],
    }
    client = FakeAnthropicClient(
        [
            text_response(
                json.dumps(recommendation_data),
                input_tokens=40,
                output_tokens=20,
            )
        ]
    )

    recommendation = triage_enquiry(
        make_enquiry(),
        client,
        JsonStore(),
        audit_dir=tmp_path,
    )
    audit_file = next(tmp_path.glob("*.jsonl"))
    events = read_events(audit_file)

    assert recommendation.label == "genuine"
    assert [event.type for event in events] == [
        "run_started",
        "model_call",
        "recommendation",
        "guard_result",
        "guard_result",
        "run_finished",
    ]
    assert events[1].tokens_in == 40
    assert events[3].guard == "referred_enquiry_id_check"
    assert events[3].guard_passed is True
    assert events[4].guard == "evidence_check"
    assert events[-1].run_succeeded is True
    assert events[-1].final_label == "genuine"
    model_call = client.messages.calls[0]
    assert "untrusted data" in model_call["system"]
    assert "<rental_enquiry>" in model_call["messages"][0]["content"]
    assert "</rental_enquiry>" in model_call["messages"][0]["content"]


def test_triage_writes_run_finished_when_loop_fails(tmp_path):
    client = FakeAnthropicClient(
        [text_response("partial", stop_reason="max_tokens")]
    )

    with pytest.raises(RuntimeError, match="Unexpected tool response"):
        triage_enquiry(
            make_enquiry(),
            client,
            JsonStore(),
            audit_dir=tmp_path,
        )

    audit_file = next(tmp_path.glob("*.jsonl"))
    events = read_events(audit_file)

    assert [event.type for event in events] == [
        "run_started",
        "model_call",
        "run_finished",
    ]
    assert events[-1].run_succeeded is False
    assert events[-1].final_label is None


def test_triage_rejects_wrong_referred_enquiry_id(tmp_path):
    recommendation_data = {
        "referred_enquiry_id": "ENQ-01",
        "duplicated_enquiry_id": None,
        "label": "genuine",
        "reason": "The enquiry contains clear rental intent.",
        "evidence": [
            {
                "source": "message",
                "quote": "looking for a studio in Griffintown",
                "support": "Provides a concrete rental request.",
            }
        ],
    }
    client = FakeAnthropicClient(
        [text_response(json.dumps(recommendation_data))]
    )

    with pytest.raises(ValueError, match="referred_enquiry_id does not match"):
        triage_enquiry(
            make_enquiry(),
            client,
            JsonStore(),
            audit_dir=tmp_path,
        )

    events = read_events(next(tmp_path.glob("*.jsonl")))

    assert [event.type for event in events] == [
        "run_started",
        "model_call",
        "recommendation",
        "guard_result",
        "run_finished",
    ]
    assert events[-2].guard == "referred_enquiry_id_check"
    assert events[-2].guard_passed is False
    assert events[-1].run_succeeded is False

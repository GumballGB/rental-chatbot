# Test just for faking the Anthropic client and testing the 
# run_tool_loop function in anthropic_functions.py
# These tests do not use the real Anthropic client, but instead use a 
# FakeAnthropicClient that can be scripted with responses.

import json

import pytest

from agents import anthropic_functions as af
from core.store import JsonStore
from core.tools import TRIAGE_SCHEMA_LIST
from tests.fakes import FakeAnthropicClient, text_response, tool_use_response


def test_run_tool_loop_plain_answer_no_tool_use():
    client = FakeAnthropicClient([text_response("Here is the answer.")])
    store = JsonStore()
    messages = [{"role": "user", "content": "Is this available?"}]

    text, updated_messages = af.run_tool_loop(messages, client, store, "test system")

    assert text == "Here is the answer."
    assert updated_messages[-1]["role"] == "assistant"
    assert client.messages.calls[0]["tools"] == af.CHATBOT_SCHEMA_LIST
    assert client.messages.calls[0]["max_tokens"] == 1024


def test_run_tool_loop_tool_use_then_end_turn():
    responses = [
        tool_use_response("get_listing", {"listing_id": "LST-001"}, tool_use_id="toolu_1"),
        text_response("I checked the listing and it is available."),
    ]
    client = FakeAnthropicClient(responses)
    store = JsonStore()
    messages = [{"role": "user", "content": "Check listing LST-001"}]

    text, updated_messages = af.run_tool_loop(messages, client, store, "test system")
    tool_result_block = updated_messages[-2]["content"][0]

    assert text == "I checked the listing and it is available."
    assert len(client.messages.calls) == 2
    assert updated_messages[-2]["role"] == "user"
    assert tool_result_block["type"] == "tool_result"
    assert tool_result_block["tool_use_id"] == "toolu_1"
    assert "LST-001" in tool_result_block["content"]


def test_run_tool_loop_stops_after_six_iterations():
    responses = [
        tool_use_response("get_listing", {"listing_id": "LST-001"}, tool_use_id=f"toolu_{i}")
        for i in range(6)
    ]
    client = FakeAnthropicClient(responses)
    store = JsonStore()
    messages = [{"role": "user", "content": "keep checking"}]

    text, updated_messages = af.run_tool_loop(messages, client, store, "test system")

    assert "trouble completing that lookup" in text
    assert updated_messages[-1]["role"] == "assistant"
    assert len(client.messages.calls) == 6


def test_run_tool_loop_raises_on_unexpected_stop_reason():
    bad_response = text_response("Partial", stop_reason="refusal")
    client = FakeAnthropicClient([bad_response])
    store = JsonStore()
    messages = [{"role": "user", "content": "hello"}]

    with pytest.raises(RuntimeError, match="Unexpected tool response: refusal"):
        af.run_tool_loop(messages, client, store, "test system")


def test_run_tool_loop_forwards_configured_output_limit_on_every_turn():
    client = FakeAnthropicClient([
        tool_use_response("get_listing", {"listing_id": "LST-001"}),
        text_response("The listing lookup is complete."),
    ])

    af.run_tool_loop(
        [{"role": "user", "content": "Check listing LST-001"}],
        client, JsonStore(), "test system", max_tokens=3072,
    )

    assert len(client.messages.calls) == 2
    assert all(call["max_tokens"] == 3072 for call in client.messages.calls)


@pytest.mark.parametrize("max_tokens", [1024, 2048])
def test_truncated_responses_raise_a_clear_error_without_retrying_or_accepting_partial_json(max_tokens):
    client = FakeAnthropicClient([
        text_response('{"label": "genuine"}', stop_reason="max_tokens", output_tokens=max_tokens),
    ])
    messages = [{"role": "user", "content": "Classify this enquiry."}]
    events = []

    with pytest.raises(RuntimeError, match=f"truncated.*max_tokens={max_tokens}"):
        af.run_tool_loop(
            messages, client, JsonStore(), "test system", max_tokens=max_tokens,
            on_event=lambda event_type, **details: events.append((event_type, details)),
        )

    assert len(client.messages.calls) == 1
    assert len(messages) == 1
    assert events[0][0] == "model_call"
    assert events[0][1]["tokens_out"] == max_tokens


@pytest.mark.parametrize("max_tokens", [0, -1])
def test_run_tool_loop_rejects_nonpositive_output_limits_before_calling_model(max_tokens):
    client = FakeAnthropicClient([])

    with pytest.raises(ValueError, match="max_tokens must be positive"):
        af.run_tool_loop([], client, JsonStore(), "test system", max_tokens=max_tokens)

    assert client.messages.calls == []


def test_extract_unit_enquiry_accepts_fake_client():
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
    client = FakeAnthropicClient([text_response(json.dumps(extracted_data))])

    enquiry, declined_fields = af.extract_enquiry_unit_enquiry(
        [{"role": "user", "content": "Extract this enquiry."}],
        client,
    )

    assert enquiry.name == "Sam"
    assert enquiry.listing_id == "LST-002"
    assert declined_fields == {"phone"}


def test_run_tool_loop_reports_model_and_tool_events_in_order():
    responses = [
        tool_use_response(
            "get_listing",
            {"listing_id": "LST-001"},
            tool_use_id="toolu_1",
        ),
        text_response(
            "The listing is available.",
            input_tokens=25,
            output_tokens=8,
        ),
    ]
    client = FakeAnthropicClient(responses)
    reported_events = []

    def collect_event(event_type, **details):
        reported_events.append((event_type, details))

    af.run_tool_loop(
        [{"role": "user", "content": "Check LST-001"}],
        client,
        JsonStore(),
        "triage system",
        on_event=collect_event,
    )

    assert [event_type for event_type, _ in reported_events] == [
        "model_call",
        "tool_call",
        "tool_result",
        "model_call",
    ]
    assert reported_events[2][1]["tool_succeeded"] is True
    assert reported_events[3][1]["tokens_in"] == 25
    assert client.messages.calls[0]["system"] == "triage system"


def test_bound_tool_arguments_override_model_values():
    responses = [
        tool_use_response(
            "find_duplicate_enquiry_candidates",
            {
                "exclude_enquiry_id": "ENQ-001",
                "received_before": "2099-01-01",
                "email": "wrong@example.com",
            },
        ),
        text_response("Done."),
    ]
    client = FakeAnthropicClient(responses)

    _, messages = af.run_tool_loop(
        [{"role": "user", "content": "Check duplicates for ENQ-011"}],
        client,
        JsonStore(),
        "triage system",
        tool_schemas=TRIAGE_SCHEMA_LIST,
        bound_tool_arguments={
            "find_duplicate_enquiry_candidates": {
                "exclude_enquiry_id": "ENQ-011",
                "received_before": "2026-10-24",
                "email": "alex.morgan@example.com",
            }
        },
    )
    tool_result = json.loads(messages[-2]["content"][0]["content"])

    assert tool_result["count"] == 1
    assert tool_result["candidates"][0]["enquiry_id"] == "ENQ-001"

# Test just for faking the Anthropic client and testing the 
# run_tool_loop function in anthropic_functions.py
# These tests do not use the real Anthropic client, but instead use a 
# FakeAnthropicClient that can be scripted with responses.

import pytest

from agents import anthropic_functions as af
from core.store import JsonStore
from tests.fakes import FakeAnthropicClient, text_response, tool_use_response


def test_run_tool_loop_plain_answer_no_tool_use():
    client = FakeAnthropicClient([text_response("Here is the answer.")])
    store = JsonStore()
    messages = [{"role": "user", "content": "Is this available?"}]

    text, updated_messages = af.run_tool_loop(messages, client, store)

    assert text == "Here is the answer."
    assert updated_messages[-1]["role"] == "assistant"
    assert client.messages.calls[0]["tools"] == af.SCHEMA_LIST


def test_run_tool_loop_tool_use_then_end_turn():
    responses = [
        tool_use_response("get_listing", {"listing_id": "LST-001"}, tool_use_id="toolu_1"),
        text_response("I checked the listing and it is available."),
    ]
    client = FakeAnthropicClient(responses)
    store = JsonStore()
    messages = [{"role": "user", "content": "Check listing LST-001"}]

    text, updated_messages = af.run_tool_loop(messages, client, store)
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

    text, updated_messages = af.run_tool_loop(messages, client, store)

    assert "trouble completing that lookup" in text
    assert updated_messages[-1]["role"] == "assistant"
    assert len(client.messages.calls) == 6


def test_run_tool_loop_raises_on_unexpected_stop_reason():
    bad_response = text_response("Partial", stop_reason="max_tokens")
    client = FakeAnthropicClient([bad_response])
    store = JsonStore()
    messages = [{"role": "user", "content": "hello"}]

    with pytest.raises(RuntimeError, match="Unexpected tool response: max_tokens"):
        af.run_tool_loop(messages, client, store)

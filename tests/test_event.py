# Testing the Event model and its validation logic.

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from models.event import Event
from models.recommendation import Recommendation


def test_event_model_import_and_valid_run_started_event():
    event = Event(
        run_id=uuid4(),
        enquiry_id="ENQ-001",
        time=datetime.now(),
        type="run_started",
        model="claude-haiku-5-5",
    )

    assert event.type == "run_started"
    assert event.enquiry_id == "ENQ-001"


def test_event_requires_model_for_run_started():
    with pytest.raises(ValidationError, match="model is required for run_started"):
        Event(
            run_id=uuid4(),
            enquiry_id="ENQ-001",
            time=datetime.now(),
            type="run_started",
        )


def test_event_requires_tokens_for_model_call():
    with pytest.raises(ValidationError, match="tokens_in and tokens_out"):
        Event(
            run_id=uuid4(),
            enquiry_id="ENQ-001",
            time=datetime.now(),
            type="model_call",
            model="claude-haiku-5-5",
        )


def test_event_rejects_negative_tokens_for_model_call():
    with pytest.raises(ValidationError):
        Event(
            run_id=uuid4(),
            enquiry_id="ENQ-001",
            time=datetime.now(),
            type="model_call",
            model="claude-haiku-5-5",
            tokens_in=-5,
            tokens_out=10,
        )


def test_event_requires_tool_fields_for_tool_result():
    with pytest.raises(ValidationError, match="tool_succeeded is required"):
        Event(
            run_id=uuid4(),
            enquiry_id="ENQ-001",
            time=datetime.now(),
            type="tool_result",
            tool="get_listing",
            tool_result='{"listing_id":"LST-001"}',
        )


def test_event_requires_guard_fields_for_guard_result():
    with pytest.raises(ValidationError, match="guard_passed is required"):
        Event(
            run_id=uuid4(),
            enquiry_id="ENQ-001",
            time=datetime.now(),
            type="guard_result",
            guard="evidence_check",
            guard_result_reason="A quote was not found in source text.",
        )


def test_event_requires_recommendation_for_recommendation_type():
    with pytest.raises(ValidationError, match="recommendation is required"):
        Event(
            run_id=uuid4(),
            enquiry_id="ENQ-001",
            time=datetime.now(),
            type="recommendation",
        )


def test_event_requires_outcome_for_run_finished():
    with pytest.raises(ValidationError, match="run_succeeded is required"):
        Event(
            run_id=uuid4(),
            enquiry_id="ENQ-001",
            time=datetime.now(),
            type="run_finished",
        )


def test_event_accepts_valid_recommendation_event():
    recommendation = Recommendation(
        referred_enquiry_id="ENQ-001",
        label="genuine",
        reason="Request details are coherent and evidence-backed.",
        evidence=[
            {
                "source": "message",
                "quote": "looking for a studio in Griffintown",
                "support": "Shows concrete location and intent.",
            }
        ],
    )

    event = Event(
        run_id=uuid4(),
        enquiry_id="ENQ-001",
        time=datetime.now(),
        type="recommendation",
        recommendation=recommendation,
    )

    assert event.type == "recommendation"
    assert event.recommendation is not None
    assert event.recommendation.label == "genuine"


def test_event_accepts_valid_run_finished_event():
    event = Event(
        run_id=uuid4(),
        enquiry_id="ENQ-001",
        time=datetime.now(),
        type="run_finished",
        run_succeeded=True,
        final_label="genuine",
    )

    assert event.type == "run_finished"
    assert event.run_succeeded is True
    assert event.final_label == "genuine"

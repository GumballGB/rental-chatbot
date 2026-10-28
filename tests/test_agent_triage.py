# Tests for the agent_triage module, specifically the triage_enquiry function.

import json

import pytest

from agents.agent_triage import triage_enquiry
from core.audit import read_events
from core.store import JsonStore

# The models
from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review
from models.triage_result import TriageResult
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

    result = triage_enquiry(
        make_enquiry(),
        client,
        JsonStore(),
        audit_dir=tmp_path,
        output_dir=tmp_path / "output",
    )
    audit_file = next(tmp_path.glob("*.jsonl"))
    events = read_events(audit_file)

    assert isinstance(result, TriageResult)
    assert result.recommendation == Recommendation.model_validate(recommendation_data)
    assert audit_file.stem == str(result.run_id)
    assert all(event.run_id == result.run_id for event in events)
    assert all(
        event.enquiry_id == result.recommendation.referred_enquiry_id
        for event in events
    )
    assert events[2].recommendation == result.recommendation
    output_path = tmp_path / "output"
    assert Enquiry.model_validate_json(
        (output_path / "enquiries" / "ENQ-001.json").read_text()
    ) == make_enquiry()
    assert Recommendation.model_validate_json(
        (output_path / "recommendations" / f"{result.run_id}.json").read_text()
    ) == result.recommendation
    review = Review.model_validate_json(
        (output_path / "reviews" / "ENQ-001" / f"{result.run_id}.json").read_text()
    )
    assert review.run_id == result.run_id
    assert review.enquiry_id == "ENQ-001"
    assert review.decision == "pending"
    assert review.recommended_label == result.recommendation.label
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


def test_retriaging_same_enquiry_returns_distinct_runs(tmp_path):
    enquiry = make_enquiry()
    recommendation_data = {
        "referred_enquiry_id": enquiry.enquiry_id,
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
        [text_response(json.dumps(recommendation_data)) for _ in range(2)]
    )
    store = JsonStore()

    first = triage_enquiry(
        enquiry, client, store, audit_dir=tmp_path, output_dir=tmp_path / "output",
    )
    second = triage_enquiry(
        enquiry, client, store, audit_dir=tmp_path, output_dir=tmp_path / "output",
    )

    assert first.run_id != second.run_id
    assert first.recommendation.referred_enquiry_id == enquiry.enquiry_id
    assert second.recommendation.referred_enquiry_id == enquiry.enquiry_id
    assert {path.stem for path in tmp_path.glob("*.jsonl")} == {
        str(first.run_id),
        str(second.run_id),
    }
    assert {path.stem for path in (tmp_path / "output/reviews/ENQ-001").glob("*.json")} == {
        str(first.run_id),
        str(second.run_id),
    }


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
            output_dir=tmp_path / "output",
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
    assert not (tmp_path / "output").exists()


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
            output_dir=tmp_path / "output",
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
    assert not (tmp_path / "output").exists()


def successful_client():
    return FakeAnthropicClient([
        text_response(json.dumps({
            "referred_enquiry_id": "ENQ-001",
            "label": "genuine",
            "reason": "Clear rental intent.",
            "evidence": [{
                "source": "message",
                "quote": "looking for a studio in Griffintown",
                "support": "States the rental intent.",
            }],
        })),
    ])


def test_triage_can_skip_output_saving(tmp_path, monkeypatch):
    def unexpected_save(*args, **kwargs):
        pytest.fail("Saving must be skipped when output_dir is None.")

    monkeypatch.setattr("agents.agent_triage.save_for_review", unexpected_save)
    result = triage_enquiry(
        make_enquiry(), successful_client(), JsonStore(),
        audit_dir=tmp_path, output_dir=None,
    )

    assert result.recommendation.label == "genuine"
    assert {path.name for path in tmp_path.iterdir()} == {f"{result.run_id}.jsonl"}


def test_triage_audits_saving_failure(tmp_path, monkeypatch):
    def failed_save(*args, **kwargs):
        raise OSError("Disk full")

    monkeypatch.setattr("agents.agent_triage.save_for_review", failed_save)
    with pytest.raises(OSError, match="Disk full"):
        triage_enquiry(
            make_enquiry(), successful_client(), JsonStore(),
            audit_dir=tmp_path, output_dir=tmp_path / "output",
        )

    events = read_events(next(tmp_path.glob("*.jsonl")))
    assert events[-1].type == "run_finished"
    assert events[-1].run_succeeded is False
    assert events[-1].final_label is None

# Tests for the agent_triage module, specifically the triage_enquiry function.

import json

import pytest
from pydantic import ValidationError

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


def make_pii_enquiry():
    return Enquiry(
        enquiry_id="ENQ-pii-test",
        name="Amélie Tremblay",
        email="amelie.tremblay@example.com",
        phone="+1 514 555 0123",
        received_date="2026-10-29",
        message=(
            "Hi, I'm Amélie Tremblay. I am looking for a studio in Griffintown. "
            "Email amelie.tremblay@example.com or call +1 514 555 0123."
        ),
    )


def test_triage_requests_do_not_include_contact_details(tmp_path):
    enquiry = make_pii_enquiry()
    # Use an unaffected quote so a privacy failure is separate from evidence validation.
    recommendation_data = {
        "referred_enquiry_id": enquiry.enquiry_id,
        "label": "genuine",
        "reason": "The enquiry contains clear rental intent.",
        "evidence": [{
            "source": "message",
            "quote": "looking for a studio in Griffintown",
            "support": "Provides a concrete rental request.",
        }],
    }
    client = FakeAnthropicClient([text_response(json.dumps(recommendation_data))])

    triage_enquiry(
        enquiry, client, JsonStore(), audit_dir=tmp_path / "audit", output_dir=None,
    )

    assert client.messages.calls, "Triage must actually make a model request."
    requests = json.dumps(client.messages.calls, ensure_ascii=False)
    assert "looking for a studio in Griffintown" in requests
    leaked_fields = [
        field for field in ("name", "email", "phone")
        if getattr(enquiry, field) in requests
    ]
    assert leaked_fields == [], f"Triage sent personal fields to the model: {leaked_fields}"
    assert "[NAME]" in requests
    assert "[EMAIL]" in requests
    assert "[PHONE]" in requests


@pytest.mark.parametrize(("quote", "accepted"), [
    ("Email [EMAIL] or call [PHONE].", True),
    ("Hi, I'm [NAME].", True),
    ("Email amelie.tremblay@example.com", False),
    ("call +1 514 555 0123.", False),
    ("Hi, I'm Amélie Tremblay.", False),
    ("Email [EMAIL] or call [PHONE] tomorrow.", False),
])
def test_triage_checks_evidence_against_the_message_sent_to_the_model(tmp_path, quote, accepted):
    enquiry = make_pii_enquiry()
    original = enquiry.model_dump()
    recommendation_data = {
        "referred_enquiry_id": enquiry.enquiry_id,
        "label": "genuine",
        "reason": "The enquiry contains a rental request.",
        "evidence": [{
            "source": "message",
            "quote": quote,
            "support": "Quotes the supplied enquiry message.",
        }],
    }
    client = FakeAnthropicClient([text_response(json.dumps(recommendation_data))])
    audit_dir = tmp_path / "audit"
    output_dir = tmp_path / "output"

    if accepted:
        result = triage_enquiry(
            enquiry, client, JsonStore(), audit_dir=audit_dir, output_dir=output_dir,
        )
        assert result.recommendation.evidence[0].quote == quote
        saved_enquiry = Enquiry.model_validate_json(
            (output_dir / "enquiries" / f"{enquiry.enquiry_id}.json").read_text(encoding="utf-8")
        )
        assert saved_enquiry.model_dump() == original
        message = client.messages.calls[0]["messages"][0]["content"]
        assert quote in message
    else:
        with pytest.raises(ValueError, match="failed evidence check"):
            triage_enquiry(
                enquiry, client, JsonStore(), audit_dir=audit_dir, output_dir=output_dir,
            )
        assert not output_dir.exists()

    events = read_events(next(audit_dir.glob("*.jsonl")))
    evidence_guard = next(event for event in events if event.guard == "evidence_check")
    assert evidence_guard.guard_passed is accepted
    assert events[-1].run_succeeded is accepted
    assert enquiry.model_dump() == original


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


def test_triage_sends_the_complete_recommendation_schema(tmp_path):
    client = successful_client()

    result = triage_enquiry(
        make_enquiry(), client, JsonStore(), audit_dir=tmp_path, output_dir=None,
    )

    system = client.messages.calls[0]["system"]
    schema = json.loads(system.split("\n\nRecommendation response JSON schema:\n", 1)[1])
    assert schema == Recommendation.model_json_schema()
    evidence_schema = schema["$defs"]["Evidence"]
    assert evidence_schema["type"] == "object"
    assert set(evidence_schema["required"]) == {"source", "quote", "support"}
    assert result.recommendation.evidence[0].source == "message"


def test_triage_rejects_plain_string_evidence_without_creating_a_review(tmp_path):
    client = FakeAnthropicClient([text_response(json.dumps({
        "referred_enquiry_id": "ENQ-001",
        "duplicated_enquiry_id": None,
        "label": "genuine",
        "reason": "Clear rental intent.",
        "evidence": ["looking for a studio in Griffintown"],
    }))])

    with pytest.raises(ValidationError) as error:
        triage_enquiry(
            make_enquiry(), client, JsonStore(),
            audit_dir=tmp_path / "audit", output_dir=tmp_path / "output",
        )

    assert error.value.errors()[0]["loc"] == ("evidence", 0)
    assert not (tmp_path / "output").exists()
    events = read_events(next((tmp_path / "audit").glob("*.jsonl")))
    assert events[-1].type == "run_finished"
    assert events[-1].run_succeeded is False


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


@pytest.mark.parametrize(("name", "email", "phone", "has_name", "has_contact"), [
    ("Amélie Tremblay", "amelie@example.com", None, True, True),
    ("Amélie Tremblay", None, "+1 514 555 0123", True, True),
    (None, "amelie@example.com", "+1 514 555 0123", False, True),
    ("Amélie Tremblay", None, None, True, False),
    (None, None, None, False, False),
])
def test_triage_sends_presence_flags_and_label_policy_without_contact_values(
    tmp_path, name, email, phone, has_name, has_contact,
):
    enquiry = make_enquiry().model_copy(update={"name": name, "email": email, "phone": phone})
    client = successful_client()

    triage_enquiry(enquiry, client, JsonStore(), audit_dir=tmp_path, output_dir=None)

    request = client.messages.calls[0]
    content = request["messages"][0]["content"]
    payload = json.loads(content.split("<rental_enquiry>\n", 1)[1].split("\n</rental_enquiry>", 1)[0])
    assert payload["has_name"] is has_name
    assert payload["has_contact"] is has_contact
    for private_value in (name, email, phone):
        if private_value:
            assert private_value not in json.dumps(request, ensure_ascii=False)
    policy = request["system"]
    for label in ("genuine", "needs_info", "spam", "duplicate"):
        assert f"{label}:" in policy
    assert "both has_name and has_contact are true" in policy
    assert "either has_name or has_contact is false" in policy
    assert "Missing listing, move-in date, budget or currency" in policy
    assert "application-computed" in policy


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

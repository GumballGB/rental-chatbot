# Test for evidence checking functions in core.evidence.py

import json

from core.evidence import find_evidence_failures, recommendation_passes_evidence_check
from models.recommendation import Recommendation


def make_recommendation(evidence_items):
    return Recommendation(
        referred_enquiry_id="ENQ-001",
        label="genuine",
        reason="Clear and consistent request.",
        evidence=evidence_items,
    )


def test_evidence_checker_passes_with_valid_message_and_tool_quotes():
    enquiry_message = (
        "Hello! I am looking for a studio in Griffintown for November. "
        "I work full-time and prefer a quiet building."
    )
    tool_output = [json.dumps({"availability_status": "available", "listing_id": "LST-001"})]

    rec = make_recommendation(
        [
            {
                "source": "message",
                "quote": "looking for a studio in Griffintown",
                "support": "States location and unit intent.",
            },
            {
                "source": "tool_result",
                "quote": '"availability_status":"available"',
                "support": "Matches listing status from tool output.",
            },
        ]
    )

    assert find_evidence_failures(rec, enquiry_message, tool_output) == []
    assert recommendation_passes_evidence_check(rec, enquiry_message, tool_output)


def test_evidence_checker_reports_missing_message_quote():
    rec = make_recommendation(
        [
            {
                "source": "message",
                "quote": "this sentence does not exist here",
                "support": "Intentionally invalid quote.",
            }
        ]
    )

    failures = find_evidence_failures(rec, "Short enquiry text.", [])

    assert len(failures) == 1
    assert failures[0].reason == "not found in message"


def test_evidence_checker_reports_missing_tool_result_quote():
    rec = make_recommendation(
        [
            {
                "source": "tool_result",
                "quote": '"availability_status":"pending"',
                "support": "Intentionally invalid tool quote.",
            }
        ]
    )

    failures = find_evidence_failures(
        rec,
        "Enquiry message.",
        [json.dumps({"availability_status": "available"})],
    )

    assert len(failures) == 1
    assert failures[0].reason == "not found in tool results"


def test_evidence_checker_tolerates_json_spacing_differences():
    rec = make_recommendation(
        [
            {
                "source": "tool_result",
                "quote": '"availability_status": "available"',
                "support": "Spacing should not matter for JSON snippets.",
            }
        ]
    )

    # Compact JSON output from model_dump_json style serialization.
    tool_output = ['{"availability_status":"available"}']

    assert find_evidence_failures(rec, "Enquiry message.", tool_output) == []


def test_evidence_checker_tolerates_curly_apostrophe_differences():
    rec = make_recommendation(
        [
            {
                "source": "message",
                "quote": "Le logement une chambre pres du centre-ville m'interesse.",
                "support": "Apostrophe normalization should allow matching.",
            }
        ]
    )

    enquiry_message = "Bonjour! Le logement une chambre pres du centre-ville m’interesse."

    assert find_evidence_failures(rec, enquiry_message, []) == []


def test_evidence_checker_is_case_sensitive():
    rec = make_recommendation(
        [
            {
                "source": "message",
                "quote": "HELLO THERE",
                "support": "Case sensitivity should be preserved.",
            }
        ]
    )

    failures = find_evidence_failures(rec, "hello there", [])

    assert len(failures) == 1
    assert failures[0].reason == "not found in message"


def test_evidence_checker_does_not_relax_message_punctuation_spacing():
    rec = make_recommendation(
        [
            {
                "source": "message",
                "quote": "flexible,really",
                "support": "Message evidence should remain close to verbatim.",
            }
        ]
    )

    enquiry_message = "I can be flexible, really."

    failures = find_evidence_failures(rec, enquiry_message, [])

    assert len(failures) == 1
    assert failures[0].reason == "not found in message"

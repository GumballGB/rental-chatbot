# Test for evidence checking functions in core.evidence.py

import json

import pytest

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


def test_evidence_checker_still_rejects_case_changes_beyond_the_initial_letter():
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


@pytest.mark.parametrize(("quote", "message"), [
    ("Jeg søger en lejlighed i København.", "Hej, jeg søger en lejlighed i København."),
    ("jeg søger en lejlighed i København.", "Jeg søger en lejlighed i København."),
    ("Écrivez-moi demain.", "Pour visiter: écrivez-moi demain."),
    ("I'm looking for a studio.", "Hello! i’m looking for a studio."),
])
def test_message_quotes_allow_initial_letter_capitalization_without_changing_evidence(quote, message):
    recommendation = make_recommendation([{
        "source": "message", "quote": quote, "support": "States a rental-related request.",
    }])
    original = recommendation.model_dump()

    assert find_evidence_failures(recommendation, message, []) == []
    assert recommendation.model_dump() == original


@pytest.mark.parametrize(("quote", "message"), [
    ("My budget is 2900 CAD.", "My budget is 1900 CAD."),
    ("Pets are allowed.", "Pets are not allowed."),
    ("Jeg søger en lejlighed i Aarhus.", "Hej, jeg søger en lejlighed i København."),
    ("Jeg søger en Lejlighed.", "Hej, jeg søger en lejlighed."),
    ("Contact us tomorrow.", "Contact US tomorrow."),
    ("Looking for a (studio).", "looking for a studio."),
    ("Studio.* please", "studio near downtown please"),
])
def test_initial_letter_tolerance_rejects_other_text_changes(quote, message):
    recommendation = make_recommendation([{
        "source": "message", "quote": quote, "support": "An altered quote must fail.",
    }])

    failures = find_evidence_failures(recommendation, message, [])

    assert len(failures) == 1
    assert failures[0].reason == "not found in message"


@pytest.mark.parametrize(("quote", "tool_result"), [
    ('"listing_id": "lst-001"', '{"listing_id": "LST-001"}'),
    ("Available listing", "available listing"),
])
def test_tool_result_identifiers_and_text_remain_case_sensitive(quote, tool_result):
    recommendation = make_recommendation([{
        "source": "tool_result", "quote": quote, "support": "References a listing identifier or status.",
    }])

    failures = find_evidence_failures(recommendation, "", [tool_result])

    assert len(failures) == 1
    assert failures[0].reason == "not found in tool results"


@pytest.mark.parametrize("source", ["message", "tool_result"])
def test_capitalization_tolerance_does_not_allow_quotes_from_the_wrong_source(source):
    recommendation = make_recommendation([{
        "source": source, "quote": "Jeg søger en lejlighed.", "support": "Requires its declared source.",
    }])
    message = "Unrelated message." if source == "message" else "Jeg søger en lejlighed."
    tools = ["Jeg søger en lejlighed."] if source == "message" else ["Unrelated tool result."]

    assert len(find_evidence_failures(recommendation, message, tools)) == 1


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

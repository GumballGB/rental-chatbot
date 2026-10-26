# Tests for the Recommendation model in models/recommendation.py

import pytest
from pydantic import ValidationError

from models.recommendation import Recommendation


def evidence_items():
    return [
        {
            "source": "message",
            "quote": "I am looking for a studio in Griffintown for November.",
            "support": "Shows clear rental intent with timing and area.",
        },
        {
            "source": "message",
            "quote": "I work full-time and prefer a quiet building.",
            "support": "Provides realistic preferences and constraints.",
        },
        {
            "source": "tool_result",
            "quote": '"availability_status":"available"',
            "support": "Confirms listing status from internal records.",
        },
    ]


def test_recommendation_accepts_one_to_five_evidence_items():
    rec_min = Recommendation(
        referred_enquiry_id="ENQ-001",
        label="genuine",
        reason="Specific and coherent request for a valid listing.",
        evidence=[evidence_items()[0]],
    )

    rec_max = Recommendation(
        referred_enquiry_id="ENQ-001",
        label="genuine",
        reason="Specific and coherent request for a valid listing.",
        evidence=evidence_items() + [evidence_items()[0], evidence_items()[1]],
    )

    assert len(rec_min.evidence) == 1
    assert len(rec_max.evidence) == 5


def test_recommendation_rejects_zero_evidence_items():
    with pytest.raises(ValidationError):
        Recommendation(
            referred_enquiry_id="ENQ-001",
            label="genuine",
            reason="Insufficient evidence test.",
            evidence=[],
        )


def test_recommendation_rejects_too_many_evidence_items():
    with pytest.raises(ValidationError):
        Recommendation(
            referred_enquiry_id="ENQ-001",
            label="genuine",
            reason="Too many evidence entries test.",
            evidence=evidence_items() + [evidence_items()[0], evidence_items()[1], evidence_items()[2]],
        )


def test_evidence_rejects_empty_quote():
    with pytest.raises(ValidationError):
        Recommendation(
            referred_enquiry_id="ENQ-001",
            label="genuine",
            reason="Quote cannot be empty.",
            evidence=[
                {
                    "source": "message",
                    "quote": "",
                    "support": "A support explanation.",
                }
            ],
        )


def test_evidence_rejects_whitespace_only_support():
    with pytest.raises(ValidationError):
        Recommendation(
            referred_enquiry_id="ENQ-001",
            label="genuine",
            reason="Support cannot be empty.",
            evidence=[
                {
                    "source": "message",
                    "quote": "Is this apartment still available?",
                    "support": "   ",
                }
            ],
        )


def test_duplicate_label_requires_duplicated_enquiry_id():
    with pytest.raises(ValidationError, match="duplicated_enquiry_id is required"):
        Recommendation(
            referred_enquiry_id="ENQ-011",
            label="duplicate",
            reason="Same contact details and same listing as prior enquiry.",
            evidence=evidence_items(),
        )


def test_non_duplicate_rejects_duplicated_enquiry_id():
    with pytest.raises(ValidationError, match="duplicated_enquiry_id must be null"):
        Recommendation(
            referred_enquiry_id="ENQ-001",
            duplicated_enquiry_id="ENQ-000",
            label="genuine",
            reason="Should not set duplicate id for non-duplicate labels.",
            evidence=evidence_items(),
        )


def test_duplicate_accepts_duplicated_enquiry_id():
    rec = Recommendation(
        referred_enquiry_id="ENQ-011",
        duplicated_enquiry_id="ENQ-004",
        label="duplicate",
        reason="Matches previous enquiry intent and identifiers.",
        evidence=evidence_items(),
    )

    assert rec.duplicated_enquiry_id == "ENQ-004"

from agents.anthropic_functions import create_enquiry
from core.store import JsonStore


def enquiry_data(listing_id):
    return {
        "name": "Sam",
        "email": "sam@example.com",
        "phone": None,
        "move_in_date": None,
        "budget": 1900,
        "message": "Interested in this listing.",
        "listing_id": listing_id,
    }


def test_create_canadian_enquiry():
    enquiry = create_enquiry(enquiry_data("LST-002"), JsonStore())

    assert enquiry.listing_id == "LST-002"
    assert enquiry.budget_currency == "CAD"
    assert enquiry.enquiry_id.startswith("ENQ-")
    assert enquiry.received_date is not None


def test_create_danish_enquiry():
    enquiry = create_enquiry(enquiry_data("LST-080"), JsonStore())

    assert enquiry.listing_id == "LST-080"
    assert enquiry.budget_currency == "DKK"
    assert enquiry.enquiry_id.startswith("ENQ-")
    assert enquiry.received_date is not None


def test_create_enquiry_with_unknown_listing():
    enquiry = create_enquiry(enquiry_data("LST-999"), JsonStore())

    assert enquiry.listing_id is None
    assert enquiry.budget_currency is None
    assert enquiry.enquiry_id.startswith("ENQ-")
    assert enquiry.received_date is not None
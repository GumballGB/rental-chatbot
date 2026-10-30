# Redaction recognises supported contacts while preserving rental information.

import pytest

from core.pii import contains_pii, enquiry_for_triage, redact_pii
from models.enquiry import Enquiry


@pytest.mark.parametrize("email", [
    "amelie@example.com",
    "amelie.tremblay+rent@example.co.uk",
    "RENTER_123@EXAMPLE.CA",
])
def test_email_addresses_are_replaced(email):
    text = f"Please contact {email} about the studio."

    assert contains_pii(text)
    assert redact_pii(text) == "Please contact [EMAIL] about the studio."


@pytest.mark.parametrize("phone", [
    "+1 514 555 0123",
    "(514) 555-0123",
    "514.555.0123",
    "514-555-0123",
    "5145550123",
    "+15145550123",
    "1-514-555-0123",
    "+45 20 30 40 50",
    "+4520304050",
    "12 34 56 78",
    "12-34-56-78",
    "12.34.56.78",
])
def test_supported_phone_formats_are_replaced(phone):
    text = f"Call me on {phone}, please."

    assert contains_pii(text)
    assert redact_pii(text) == "Call me on [PHONE], please."


@pytest.mark.parametrize(("text", "expected"), [
    ("Units: 45 50 55 60 sqm", "Units: [PHONE] sqm"),
    ("Viewing 10 11 12 13 pm", "Viewing [PHONE] pm"),
])
def test_grouped_number_lists_are_an_accepted_phone_false_positive(text, expected):
    # Prefer hiding an ambiguous sequence over leaking a local phone number.
    assert contains_pii(text)
    assert redact_pii(text) == expected


@pytest.mark.parametrize("text", [
    "My budget is 1900 CAD.",
    "Move-in date: 2026-10-28.",
    "Listing LST-001 and enquiry ENQ-5145550123.",
    "Dates: 2026-10-28 and 2026-12-01.",
    "Please email me about the studio.",
    "The password field and credit card field are not needed here.",
    "Received 20261028; listing LST-12-34-56-78.",
    "These figures are split over lines: 12 34\n56 78.",
])
def test_rental_details_and_keywords_are_not_mistaken_for_contacts(text):
    assert not contains_pii(text)
    assert redact_pii(text) == text


@pytest.mark.parametrize("spelling", ["Amélie", "amélie", "AMÉLIE", "Amelie", "amelie", "AMELIE"])
def test_known_name_is_replaced_case_insensitively(spelling):
    text = f"Hi, I'm {spelling}. Is the studio available?"

    assert contains_pii(text, name="Amélie")
    assert redact_pii(text, name="Amélie") == "Hi, I'm [NAME]. Is the studio available?"


def test_known_name_is_literal_and_not_part_of_a_longer_word():
    assert redact_pii("Amélienne mentioned Amélie.", name="Amélie") == "Amélienne mentioned [NAME]."
    assert redact_pii("Contact Al(bert)+ today.", name="Al(bert)+") == "Contact [NAME] today."


@pytest.mark.parametrize(("text", "expected"), [
    ("Hi, I'm Amélie Tremblay.", "Hi, I'm [NAME]."),
    ("Hi, I'm amelie tremblay.", "Hi, I'm [NAME]."),
    ("Hi, I'm Amélie.", "Hi, I'm [NAME]."),
    ("Hi, I'm Amelie.", "Hi, I'm [NAME]."),
    ("Tremblay here.", "[NAME] here."),
])
def test_full_name_and_longer_capitalised_parts_are_replaced(text, expected):
    assert contains_pii(text, name="Amélie Tremblay")
    assert redact_pii(text, name="Amélie Tremblay") == expected


@pytest.mark.parametrize(("name", "text", "expected"), [
    ("Emil Sørensen", "Emil Sørensen / Sorensen", "[NAME] / [NAME]"),
    ("Emil Sørensen", "emil sorensen", "[NAME]"),
    ("Klara Kjær", "Kjær / Kjaer", "[NAME] / [NAME]"),
    ("Østergaard", "Ostergaard", "[NAME]"),
    ("Ægir Holm", "Aegir / AEgir", "[NAME] / [NAME]"),
    ("ÆGIR HOLM", "AEGIR here", "[NAME] here"),
    ("Amélie Søndergaard", "Amelie Sondergaard", "[NAME]"),
    ("Sørensen", "Sørensen søger et værelse i København.", "[NAME] søger et værelse i København."),
])
def test_danish_names_accept_explicit_ascii_spellings(name, text, expected):
    assert contains_pii(text, name=name)
    assert redact_pii(text, name=name) == expected


@pytest.mark.parametrize(("name", "text", "expected"), [
    ("Nina Park", "Nina wants to live near a park.", "[NAME] wants to live near a park."),
    ("Taylor Kim", "Taylor here. Kim will visit.", "[NAME] here. Kim will visit."),
    ("Jordan Lee", "Jordan here. Lee will visit.", "[NAME] here. Lee will visit."),
    ("Thomas Reed", "Thomas likes the reed beds. Reed here.", "[NAME] likes the reed beds. [NAME] here."),
])
def test_partial_name_rule_limits_common_word_false_positives(name, text, expected):
    assert redact_pii(text, name=name) == expected


def test_short_full_names_still_match_even_though_short_parts_do_not():
    assert redact_pii("Kim here.", name="Kim") == "[NAME] here."
    assert redact_pii("Taylor Kim here.", name="Taylor Kim") == "[NAME] here."


def test_lowercase_parts_and_capitalised_common_words_are_documented_limits():
    # Avoiding lowercase ordinary words also misses lowercase partial signatures.
    assert redact_pii("nina here, near a park.", name="Nina Park") == "nina here, near a park."
    # Capitalisation cannot distinguish this ordinary word from the surname.
    assert redact_pii("Park nearby, please.", name="Nina Park") == "[NAME] nearby, please."


@pytest.mark.parametrize(("name", "part"), [
    ("Taylor Kim", "Kim"), ("Jordan Lee", "Lee"), ("Jo Hansen", "Jo"),
    ("Li Jensen", "Li"), ("Bo Nielsen", "Bo"),
])
def test_short_partial_names_remain_a_documented_limit(name, part):
    text = f"Please see {part}."

    assert not contains_pii(text, name=name)
    assert redact_pii(text, name=name) == text


def test_lowercase_partial_signature_remains_a_documented_limit():
    text = "sofie here"

    assert not contains_pii(text, name="Sofie Andersen")
    assert redact_pii(text, name="Sofie Andersen") == text


@pytest.mark.parametrize("name", [None, "", " \t "])
def test_missing_known_name_does_not_change_text(name):
    text = "Hi, I'm Amélie. I want a studio."

    assert not contains_pii(text, name=name)
    assert redact_pii(text, name=name) == text


def test_unknown_names_are_a_documented_limit():
    text = "Hi, I'm Sam. Amélie referred me."

    assert redact_pii(text, name="Amélie") == "Hi, I'm Sam. [NAME] referred me."


def test_redaction_preserves_accents_newlines_spacing_and_rental_details():
    text = (
        "  Bonjour, je suis Amélie.\n"
        "Je cherche un studio à Montréal.\n\n"
        "Budget: 1900 CAD; date: 2026-10-28; listing: LST-001.\n"
        "Écrivez à amelie@example.com ou appelez le (514) 555-0123.  "
    )

    assert redact_pii(text, name="Amélie") == (
        "  Bonjour, je suis [NAME].\n"
        "Je cherche un studio à Montréal.\n\n"
        "Budget: 1900 CAD; date: 2026-10-28; listing: LST-001.\n"
        "Écrivez à [EMAIL] ou appelez le [PHONE].  "
    )


def test_names_inside_contacts_do_not_prevent_contact_redaction():
    text = "Sam: sam@example.com, +1 514 555 0123."

    assert redact_pii(text, name="Sam") == "[NAME]: [EMAIL], [PHONE]."


def test_empty_text_is_supported():
    assert not contains_pii("")
    assert redact_pii("") == ""


def test_model_facing_view_has_only_allowed_fields_and_preserves_the_original():
    enquiry = Enquiry(
        enquiry_id="ENQ-001",
        name="Amélie",
        email="amelie@example.com",
        phone="+1 514 555 0123",
        message="Amélie here. Email amelie@example.com or call +1 514 555 0123.",
        listing_id="LST-001",
        budget=1900,
        budget_currency="CAD",
        received_date="2026-10-29",
        move_in_date="2026-12-01",
    )
    before = enquiry.model_dump()

    view = enquiry_for_triage(enquiry)

    assert view == {
        "enquiry_id": "ENQ-001",
        "listing_id": "LST-001",
        "budget": 1900,
        "budget_currency": "CAD",
        "received_date": "2026-10-29",
        "move_in_date": "2026-12-01",
        "has_name": True,
        "has_contact": True,
        "message": "[NAME] here. Email [EMAIL] or call [PHONE].",
    }
    assert enquiry.model_dump() == before


def test_model_facing_view_handles_optional_fields_and_zero_budget():
    enquiry = Enquiry(enquiry_id="ENQ-empty", budget=0)

    view = enquiry_for_triage(enquiry)

    assert view["message"] is None
    assert view["budget"] == 0
    assert "name" not in view
    assert "email" not in view
    assert "phone" not in view


@pytest.mark.parametrize(("name", "email", "phone", "has_name", "has_contact"), [
    ("Amélie", "amelie@example.com", None, True, True),
    ("Amélie", None, "+1 514 555 0123", True, True),
    (None, "amelie@example.com", "+1 514 555 0123", False, True),
    ("Amélie", None, None, True, False),
    (None, None, None, False, False),
    ("", None, "", False, False),
    (" \t ", None, " \t ", False, False),
    (" Amélie ", None, " +1 514 555 0123 ", True, True),
])
def test_presence_flags_use_nonblank_fields_without_inferring_from_the_message(
    name, email, phone, has_name, has_contact,
):
    enquiry = Enquiry(
        enquiry_id="ENQ-flags", name=name, email=email, phone=phone,
        message="Hi, I'm Amélie. Email amelie@example.com or call +1 514 555 0123.",
    )
    original = enquiry.model_dump()

    view = enquiry_for_triage(enquiry)

    assert view["has_name"] is has_name
    assert view["has_contact"] is has_contact
    assert {"name", "email", "phone"}.isdisjoint(view)
    assert enquiry.model_dump() == original

# Recognise supported contacts and prepare a filtered enquiry for triage.

"""
These pattern-based helpers do not identify all personal information. They
support common emails, North American phones, Danish +45 and grouped local
numbers, and a supplied full name or selected parts. Unknown names remain.
"""

import re
import unicodedata

from models.enquiry import Enquiry

EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"

# Danish letters are not in the ASCII range, so we provide a translation table
DANISH_ASCII = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE"})
DANISH_ASCII_TITLE = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae"})

# Require the full number, keeping short budgets and ISO dates intact.
# Word and hyphen boundaries also avoid matching numbers inside IDs.
# Use spaces/tabs rather than \s so matches do not consume line breaks.
PHONE_PATTERN = (
    r"(?<![\w+-])(?:"
    r"(?:\+?1[ \t.-]*)?(?:\([2-9]\d{2}\)|[2-9]\d{2})[ \t.-]*\d{3}[ \t.-]*\d{4}"
    r"|\+45[ \t.-]*(?:\d{2}[ \t.-]*){3}\d{2}"
    # Intentionally accepts ambiguous numeric lists without a phone cue.
    r"|\d{2}(?:[ \t.-]+\d{2}){3}"
    r")(?![\w-])"
)


def _name_spellings(name: str) -> list[str]:
    """Accept supplied, accent-free, and explicit Danish-to-ASCII spellings."""

    accent_free = "".join(
        character for character in unicodedata.normalize("NFD", name)
        if not unicodedata.combining(character)
    )
    spellings = [name, accent_free]

    # Add Danish-to-ASCII spellings for each of the above, keeping the original case.
    for spelling in (name, accent_free):
        spellings.extend([
            spelling.translate(DANISH_ASCII),
            spelling.translate(DANISH_ASCII_TITLE),
        ])
    return list(dict.fromkeys(spelling for spelling in spellings if spelling))


def _pii_pattern(name: str | None) -> re.Pattern[str]:
    """
    Match a full name ignoring case, or parts of 4+ letters in supplied case.
    However, names like Kim, Jo Lee will pass through, as they are too short to be considered PII.
    It is a trade-off between false positives and false negatives, but we prefer to err on the side of caution.
    """

    parts = [f"(?P<EMAIL>{EMAIL_PATTERN})", f"(?P<PHONE>{PHONE_PATTERN})"]

    known_name = name.strip() if name else "" # Check the name as well

    if known_name:
        # The inline flag applies only to the full name, keeping partial names
        # case-sensitive so a surname Park does not match the ordinary word park.
        full_name = "|".join(re.escape(spelling) for spelling in _name_spellings(known_name))
        name_alternatives = [f"(?i:{full_name})"]

        # Add any parts of the name that are not the full name and have at least four letters.
        for word in known_name.split():

            # Only add the part if it is not the full name and has at least four letters.
            if word != known_name and sum(character.isalpha() for character in word) >= 4:
                name_alternatives.extend(re.escape(spelling) for spelling in _name_spellings(word))

        name_pattern = "|".join(name_alternatives)

        # Prefer the full name before parts and never match inside a longer word.
        parts.append(r"(?P<NAME>(?<!\w)(?:" + name_pattern + r")(?!\w))")

    return re.compile("|".join(parts))


def contains_pii(text: str, name: str | None = None) -> bool:
    """Check supported contacts and the known-name rule, not all kinds of PII."""

    return _pii_pattern(name).search(text) is not None


def redact_pii(text: str, name: str | None = None) -> str:
    """Replace matches with [EMAIL], [PHONE], or [NAME], preserving other text.

    Contacts are matched before names in one pass so replacing a name inside
    an email cannot break email detection. The input string is not modified.
    Full names ignore case; individual parts need at least four letters and
    the supplied capitalisation. Accent-free and Danish-to-ASCII spellings
    are also accepted; these alternatives do not normalise the message itself.
    """

    return _pii_pattern(name).sub(lambda match: f"[{match.lastgroup}]", text)


def enquiry_for_triage(enquiry: Enquiry) -> dict[str, str | int | bool | None]:
    """Return redacted rental fields and contact-presence flags, not contacts.

    Presence means a nonblank structured field. Details mentioned only in the
    message do not count; extraction belongs to the chatbot. Leave the original
    enquiry intact for the human reviewer.
    """

    fields = {
        "enquiry_id": enquiry.enquiry_id,
        "listing_id": enquiry.listing_id,
        "budget": enquiry.budget,
        "budget_currency": enquiry.budget_currency,
        "received_date": enquiry.received_date,
        "move_in_date": enquiry.move_in_date,
        "has_name": bool(enquiry.name and enquiry.name.strip()),
        "has_contact": any(
            value and value.strip() for value in (enquiry.email, enquiry.phone)
        ),
        "message": (
            redact_pii(enquiry.message, name=enquiry.name)
            if enquiry.message is not None else None
        ),
    }

    return fields

"""
Evidence checker for triage recommendations.

Quote: a short snippet claimed as evidence in a Recommendation item.
Text: the source body where that quote must be found (either enquiry message
or a tool result string).
"""

import re
import unicodedata

from models.evidence_failure import EvidenceFailure
from models.recommendation import Recommendation

# Map typographic quotes to plain ASCII so model/user punctuation variants can match.
_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)


def _normalize_for_match(text: str, source: str) -> str:
    """
    Normalize text for stable quote matching while preserving case sensitivity.

    Rules:
    - Keep case as-is.
    - Normalize Unicode to NFKC.
    - Convert curly quotes/apostrophes to straight variants.
    - Collapse whitespace runs to a single space.
    - For tool_result only, remove optional whitespace around JSON punctuation
      so compact and pretty JSON snippets can match consistently.
    """

    normalized = unicodedata.normalize("NFKC", text).translate(_QUOTE_TRANSLATION)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if source == "tool_result":
        normalized = re.sub(r"\s*([{}\[\]:,])\s*", r"\1", normalized)

    return normalized


def _quote_in_text(quote: str, text: str, source: str) -> bool:
    # Fast path: exact substring match before normalization fallback.
    if quote in text:
        return True

    normalized_quote = _normalize_for_match(quote, source)
    normalized_text = _normalize_for_match(text, source)

    # Allow a quote to be found anywhere in the text, even if it is a substring of a larger word.
    if normalized_quote in normalized_text:
        return True

    # A quote taken from the middle of a sentence may capitalize its first
    # letter. Allow only that character to differ, only for message evidence.
    # Escape the quote so its contents cannot become a regular expression.
    if source == "message" and normalized_quote:
        pattern = f"(?i:{re.escape(normalized_quote[0])})" + re.escape(normalized_quote[1:])
        return re.search(pattern, normalized_text) is not None
    return False


def find_evidence_failures(
    recommendation: Recommendation,
    enquiry_message: str,
    tool_results: list[str],
) -> list[EvidenceFailure]:
    """
    Return all evidence entries that fail source-scoped quote checks.

    - source=message: quote must be found in enquiry_message.
    - source=tool_result: quote must be found in at least one tool result.
    - Message quotes may differ in the capitalization of their initial letter;
      other case changes are rejected. Tool-result case is preserved throughout.
    """

    failures: list[EvidenceFailure] = []

    # Validate each evidence item against its claimed source.
    for index, item in enumerate(recommendation.evidence):
        if item.source == "message":
            # Message evidence must be found in the renter's message text.
            if not _quote_in_text(item.quote, enquiry_message, source="message"):
                failures.append(
                    EvidenceFailure(
                        index=index,
                        evidence=item,
                        reason="not found in message",
                    )
                )
            continue

        found_in_tool_result = any(
            _quote_in_text(item.quote, tool_text, source="tool_result")
            for tool_text in tool_results
        )

        # Tool evidence must be found in at least one recorded tool output.
        if not found_in_tool_result:
            failures.append(
                EvidenceFailure(
                    index=index,
                    evidence=item,
                    reason="not found in tool results",
                )
            )

    return failures


def recommendation_passes_evidence_check(
    recommendation: Recommendation,
    enquiry_message: str,
    tool_results: list[str],
) -> bool:
    return (
        len(find_evidence_failures(recommendation, enquiry_message, tool_results)) == 0
    )

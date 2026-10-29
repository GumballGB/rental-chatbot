# File dedicated to having a human review process for rental enquiries and recommendations (HITL).

import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from core.writer import DEFAULT_OUTPUT_DIR, ReviewAlreadyDecidedError, save_review
from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review
from models.review_item import ReviewItem, ReviewLoadError

# A placeholder for the pydantic BaseModel variable
# It is needed to valiadate the models.
Model = TypeVar("Model", bound=BaseModel)


def _load_model(path: Path, model: type[Model], kind: str) -> Model:
    """
    Read a saved model (data) and give file problems a useful, consistent error.
    The model class to be returned is most often Review.

    """

    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ReviewLoadError(f"{kind} file missing: {path}") from error
    except UnicodeError as error:
        raise ReviewLoadError(f"Invalid {kind} UTF-8 text: {path}") from error
    except OSError as error:
        raise ReviewLoadError(f"Cannot read {kind} file {path}: {error.strerror}") from error

    # At this point, content was loaded, but it needs to be validated
    try:
        return model.model_validate_json(contents)
    except ValidationError as error:
        # Raise a ReviewLoadError if the model data is invalid or does not match the expected structure.
        raise ReviewLoadError(f"Invalid {kind} JSON or model data: {path}") from error


def load_review_item(
    review_path: str | Path, output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> ReviewItem:
    """
    Load all three models, checking their paths, links, outcome, and date.

    It will first load the review file, obtaining the enquiry ID and run ID, 
    then load the corresponding enquiry and recommendation files. It then checks that the IDs and 
    recommended outcome match across the three models, and that the enquiry's received date is 
    valid if present. Raises ReviewLoadError for missing or corrupt files and inconsistent data.
    Reading an item never changes its saved files.

    Args:
        review_path: The path to the review JSON file. 
        output_dir: The base directory where the enquiry and recommendation files are located.
    Returns:
        A ReviewItem containing the loaded review, enquiry, and recommendation models.
    """

    review_path = Path(review_path)
    output_path = Path(output_dir)
    review = _load_model(review_path, Review, "review")

    # Verify the ID before using it to locate other files.
    if not re.fullmatch(r"[A-Za-z0-9_-]+", review.enquiry_id):
        raise ReviewLoadError(f"Review path does not match a safe enquiry ID: {review_path}")

    # Verify the review path matches the expected location based on the enquiry ID and run ID.
    
    expected_path = output_path / "reviews" / review.enquiry_id / f"{review.run_id}.json"

    if review_path.resolve() != expected_path.resolve():
        raise ReviewLoadError(f"Review path does not match its enquiry ID and run ID: {review_path}")

    # Now verify the linked enquiry

    enquiry_path = output_path / "enquiries" / f"{review.enquiry_id}.json"

    enquiry = _load_model(enquiry_path, Enquiry, "enquiry")
    if enquiry.enquiry_id != review.enquiry_id:
        raise ReviewLoadError(f"Enquiry ID does not match the review: {enquiry_path}")

    # Now verify the linked recommendation

    recommendation_path = output_path / "recommendations" / f"{review.run_id}.json"

    recommendation = _load_model(recommendation_path, Recommendation, "recommendation")
    if recommendation.referred_enquiry_id != review.enquiry_id:
        raise ReviewLoadError(f"Recommendation enquiry ID does not match the review: {recommendation_path}")
    if (
        review.recommended_label != recommendation.label
        or review.recommended_duplicated_enquiry_id != recommendation.duplicated_enquiry_id
    ):
        raise ReviewLoadError(f"Recommended outcome does not match the recommendation: {review_path}")

    # Finally, verify the enquiry's received date is valid if present.

    if enquiry.received_date is not None:
        try:
            date.fromisoformat(enquiry.received_date)
        except ValueError as error:
            raise ReviewLoadError(
                f"Invalid enquiry received_date; expected an ISO date: {enquiry_path}"
            ) from error

    # At this point, all three models have been loaded and validated, and their links and data are consistent.

    return ReviewItem(review=review, enquiry=enquiry, recommendation=recommendation)


def find_pending_reviews(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> tuple[list[ReviewItem], list[str]]:
    """
    Return pending items ordered by received date, enquiry ID, then run ID.

    Missing dates sort last. Broken items are skipped with warnings, returned
    for the interface to display through show. Decided reviews are excluded
    without loading their linked bodies. No output directory means no work.

    Args:
        output_dir: The base directory where the review, enquiry, and recommendation files are located.
    Returns:
        A tuple containing a list of ReviewItem objects for pending reviews and a list of warning messages
        for any skipped or broken items. The list of ReviewItem objects is sorted by received date
    """

    output_path = Path(output_dir)
    items: list[ReviewItem] = []
    warnings: list[str] = []

    for review_path in sorted((output_path / "reviews").glob("*/*.json")):

        if not review_path.is_file():
            continue
        try:
            review = _load_model(review_path, Review, "review")
            if review.decision != "pending":
                continue
            items.append(load_review_item(review_path, output_path))
        except ReviewLoadError as error:
            warnings.append(f"Skipping review {review_path}: {error}")

    # Sort the items by received date, enquiry ID, and run ID. Missing dates sort last.
    items.sort(key=lambda item: (
        item.enquiry.received_date is None,
        date.fromisoformat(item.enquiry.received_date) if item.enquiry.received_date is not None else date.max,
        item.review.enquiry_id,
        str(item.review.run_id),
    ))
    return items, warnings

# Helper function to display a value or a marker for missing values.
def _display_value(value: str | int | None) -> str:
    """Use one marker for missing values, preserving zero and supplied text."""

    return "not provided" if value is None or value == "" else str(value)


def render_review_item(item: ReviewItem, position: int, total: int) -> str:
    """
    Return the review display using a one-based position supplied by the caller.

    Includes the full enquiry, recommendation, and evidence. Message text is
    preserved between labelled separators. Rendering only returns a string;
    it does not print, prompt, load files, or change the item.

    args:
        item: The ReviewItem to render.
        position: The one-based position of this review in the list of pending reviews.
        total: The total number of pending reviews.
    returns:
        A string containing the formatted review display, including the header, 
        enquiry details, recommendation, and evidence.
    """

    enquiry = item.enquiry
    recommendation = item.recommendation
    budget = "not provided" # budget and currency are displayed together, so we start with a default for both.

    # If either the budget or currency is provided, display them together.
    if enquiry.budget is not None or enquiry.budget_currency is not None:
        budget = f"{_display_value(enquiry.budget)} {_display_value(enquiry.budget_currency)}"

    # Build the lines of the review display, including the header, enquiry details, recommendation, and evidence.
    lines = [
        f"Review {position} of {total}",
        f"Enquiry: {enquiry.enquiry_id}",
        f"Run: {item.review.run_id}",
        f"Received: {_display_value(enquiry.received_date)}",
        "",
        f"Name: {_display_value(enquiry.name)}",
        f"Email: {_display_value(enquiry.email)}",
        f"Phone: {_display_value(enquiry.phone)}",
        f"Listing: {_display_value(enquiry.listing_id)}",
        f"Budget: {budget}",
        f"Move-in date: {_display_value(enquiry.move_in_date)}",
        "",
        "--- Enquiry message (verbatim) ---",
        _display_value(enquiry.message),
        "--- End enquiry message ---",
        "",
        f"Recommended label: {recommendation.label}",
    ]

    # If the recommendation is a duplicate, include the duplicated enquiry ID in the display.
    if recommendation.label == "duplicate":
        lines.append(f"Duplicate of: {recommendation.duplicated_enquiry_id}")
    lines.extend([
        "", "Reason:", recommendation.reason, "", "Evidence:",
        (
            "Note: Evidence quotes use the redacted text seen by triage; "
            "the original enquiry message is shown above."
        ),
    ])

    # Add each evidence item with its source, quote, and support.
    for index, evidence in enumerate(recommendation.evidence, start=1):
        lines.extend([
            f'{index}. [{evidence.source}] "{evidence.quote}"',
            f"   Support: {evidence.support}",
        ])
    return "\n".join(lines) + "\n"


def ask_for_decision(
    item: ReviewItem,
    reviewer: str,
    ask: Callable[[str], str] = input,
    show: Callable[[str], None] = print,
) -> Review | Literal["skip", "quit"]:
    """
    Collect a validated human decision without saving or changing the item.

    The menu accepts a/o/s/q, ignoring case and surrounding whitespace.
    An empty approval comment becomes None. Overrides require an explanation
    and a changed outcome; duplicate outcomes also require an enquiry ID.
    Invalid overrides display the Review validation error and repeat the form.
    Skip and quit return distinct strings. EOF or Ctrl-C at any prompt quits.
    """

    # Display the review item to the reviewer. It consists of a nested while loop.
    try:

        while True:

            # Display the review item to the reviewer.
            choice = ask("Decision: [a]pprove, [o]verride, [s]kip, [q]uit: ").strip().casefold()

            # Handle the skip and quit options, returning distinct strings for each.
            if choice == "s":
                return "skip"
            if choice == "q":
                return "quit"
            if choice not in {"a", "o"}:
                show("Unrecognised choice. Choose a, o, s, or q.")
                continue

            # Handle the approve and override options, collecting the necessary information from the reviewer.
            while True:

                # If reviewer chooses to approve, use the recommended label and duplicate ID,
                # and collect an optional comment.
                if choice == "a":

                    final_label = item.review.recommended_label
                    duplicate_id = item.review.recommended_duplicated_enquiry_id

                    message = ask("Comment (optional; Enter for none): ").strip() or None

                else:

                    final_label = ask(
                        "New label (genuine, needs_info, spam, duplicate): "
                    ).strip().casefold()
                    duplicate_id = None

                    # If the final label is "duplicate", prompt for the duplicate enquiry ID.
                    if final_label == "duplicate":
                        duplicate_id = ask("Duplicate enquiry ID: ").strip() or None

                    message = ask("Explanation for override (required): ").strip() or None

                # Validate the override requirements: explanation is required,
                # and the final outcome must differ from the recommended outcome.
                try:

                    decision_state = "approved" if choice == "a" else "overridden"

                    # Construct a new Review so its validators check the whole decision.
                    return Review.model_validate({
                        **item.review.model_dump(),
                        "decision": decision_state,
                        "reviewer": reviewer,
                        "review_date": datetime.now(UTC),
                        "message": message,
                        "final_label": final_label,
                        "final_duplicated_enquiry_id": duplicate_id,
                    })

                # If the validation fails, display the error and repeat the form.
                except ValidationError as error:

                    show(f"Invalid review: {error}")

    # If somehow the try did not work, we catch EOFError and KeyboardInterrupt to return "quit" without crashing.
    except (EOFError, KeyboardInterrupt):
        return "quit"


def run_manual_review(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    reviewer: str = "admin",
    ask: Callable[[str], str] = input,
    show: Callable[[str], None] = print,
) -> dict[str, int]:
    """
    Find pending reviews, display each item, collect decisions, and save them.

    Count approvals and overrides only after a successful save. Explicit skips
    and already-decided items count as skipped. Discovery warnings and
    already-decided items count as warned. Quitting leaves the current and
    unvisited items unchanged without counting them as skipped.

    We use the ask and show callables to allow for testing without keyboard input or output.

    Other saving errors propagate to the caller. Tests can supply a temporary
    output directory and replace ask and show without keyboard interaction.
    """
    show("Manual review process started.")
    output_path = Path(output_dir)

    # -*-*- FIND PENDING REVIEWS PHASE -*-*- #

    pending_reviews, warnings = find_pending_reviews(output_path)
    counts = {"approved": 0, "overridden": 0, "skipped": 0, "warned": len(warnings)}
    total = len(pending_reviews)
    show(f"Found {total} pending reviews.")

    for warning in warnings:
        show(f"Warning: {warning}")

    # -*-*- DECISION PHASE -*-*- #

    for position, item in enumerate(pending_reviews, start=1):

        # Display the review item and collect a decision from the reviewer.
        review_path = output_path / "reviews" / item.review.enquiry_id / f"{item.review.run_id}.json"
        show(render_review_item(item, position, total))
        decision = ask_for_decision(item, reviewer=reviewer, ask=ask, show=show)

        if decision == "skip":
            counts["skipped"] += 1
            show(f"Skipping review {review_path}.")
            continue
        if decision == "quit":
            show("Quitting the manual review process.")
            break

        # Save the decision to the output directory, handling already-decided reviews.
        try:
            saved_path = save_review(decision, output_path)
        except ReviewAlreadyDecidedError as error:
            counts["skipped"] += 1
            counts["warned"] += 1
            show(f"Skipping review {review_path}: {error}")
            continue

        counts[decision.decision] += 1
        show(f"Saved decision for review {item.review.run_id} to {saved_path}")

    show(
        f"Review summary: {counts['approved']} approved, {counts['overridden']} overridden, "
        f"{counts['skipped']} skipped, {counts['warned']} warned."
    )
    return counts

# Thin wrapper now, asks for reviwer name
def manual_review() -> dict[str, int] | None:
    """Read the reviewer name and start a terminal review session."""

    # -*-*- REVIEWER NAME PHASE -*-*- #
    try:
        reviewer = input("Reviewer name [admin]: ").strip() or "admin"
    except (EOFError, KeyboardInterrupt):
        return None

    # -*-*- MANUAL REVIEW PHASE -*-*- #
    return run_manual_review(reviewer=reviewer)


if __name__ == "__main__":
    manual_review()

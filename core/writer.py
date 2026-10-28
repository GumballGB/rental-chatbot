"""Save runtime enquiries, recommendations, and human reviews outside seed data."""

import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel

# the models
from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review
from models.triage_result import TriageResult

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


class ReviewAlreadyDecidedError(ValueError):
    """A saved human decision cannot be replaced, even by an identical save."""


class RecommendationNotFoundError(FileNotFoundError):
    """The recommendation required to validate a review has not been saved."""


# Helper function to ensure enquiry IDs are safe for filenames and directory components
def _enquiry_filename(enquiry_id: str) -> str:
    """Keep enquiry IDs within a single filename or directory component."""

    if not re.fullmatch(r"[A-Za-z0-9_-]+", enquiry_id):
        raise ValueError("enquiry_id must contain only letters, numbers, underscores, or hyphens.")

    return enquiry_id


def _atomic_save(model: BaseModel, path: Path) -> Path:
    """
    Replace a JSON file only after its complete replacement has been written.
    We use a temporary file in the same directory to ensure that the rename operation is atomic.
    This prevents partial writes from leaving a corrupted file if the process is interrupted.
    """

    # Write the model to a temporary file, then rename it to the target path.
    contents = model.model_dump_json(indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:

        # The same directory ensures that rename stays on the same filesystem.
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temporary:
            # Write the contents to the temporary file and flush to ensure it's written to disk.
            temporary_path = Path(temporary.name)
            temporary.write(contents)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        # If the temporary file still exists (e.g., due to an exception), remove it.
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return path


def save_enquiry(enquiry: Enquiry, output_dir: str | Path = DEFAULT_OUTPUT_DIR,) -> Path:
    """Save the full enquiry body, including enquiries created by the chatbot."""

    # Revalidate because Pydantic objects can be changed after construction.
    enquiry = Enquiry.model_validate(enquiry.model_dump())
    enquiry_id = _enquiry_filename(enquiry.enquiry_id)

    return _atomic_save(enquiry, Path(output_dir) / "enquiries" / f"{enquiry_id}.json")


def save_review(review: Review, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    """Save a review, replacing an existing file only while it is pending.

    Raises ReviewAlreadyDecidedError if a saved review is approved or overridden,
    including attempts to save the same decision again or reset it to pending.
    Raises RecommendationNotFoundError if the run's recommendation is missing.
    This terminal workflow supports one reviewer at a time; concurrent writes
    are outside its scope.
    """

    # Revalidate because Pydantic objects can be changed after construction.
    review = Review.model_validate(review.model_dump())
    enquiry_id = _enquiry_filename(review.enquiry_id)
    output_path = Path(output_dir)
    review_path = output_path / "reviews" / enquiry_id / f"{review.run_id}.json"

    try:
        saved_contents = review_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    else:
        saved_review = Review.model_validate_json(saved_contents)
        if saved_review.decision != "pending":
            raise ReviewAlreadyDecidedError(
                f"Review for enquiry {review.enquiry_id}, run {review.run_id} "
                f"is already {saved_review.decision} and cannot be replaced."
            )

    # Validate that the review refers to a saved recommendation and its original outcome.
    recommendation_path = output_path / "recommendations" / f"{review.run_id}.json"
    try:
        contents = recommendation_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RecommendationNotFoundError(
            f"Cannot save review for enquiry {review.enquiry_id}, run {review.run_id}: "
            f"recommendation not found at {recommendation_path}."
        ) from error
    recommendation = Recommendation.model_validate_json(contents)

    if (
        recommendation.referred_enquiry_id != review.enquiry_id
        or recommendation.label != review.recommended_label
        or recommendation.duplicated_enquiry_id != review.recommended_duplicated_enquiry_id
    ):
        raise ValueError("Review must refer to the saved recommendation and its original outcome.")
    return _atomic_save(review, review_path)


def save_for_review(enquiry: Enquiry, result: TriageResult, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Review:
    """Save both bodies, then publish a pending review linking them together.

    Each file is saved atomically. The three files are not one transaction:
    an interrupted save may leave an enquiry or recommendation without a review.
    Saving the review last keeps incomplete bundles out of the pending queue.
    """

    # Revalidate because Pydantic objects can be changed after construction.
    recommendation = Recommendation.model_validate(result.recommendation.model_dump())
    if recommendation.referred_enquiry_id != enquiry.enquiry_id:
        raise ValueError("Recommendation must refer to the enquiry being saved.")

    # Create a pending review linking the enquiry and recommendation, then save it.
    review = Review(
        enquiry_id=enquiry.enquiry_id,
        run_id=result.run_id,
        recommended_label=recommendation.label,
        recommended_duplicated_enquiry_id=recommendation.duplicated_enquiry_id,
        decision="pending", # mark it pending until a human reviewer makes a decision
    )

    # Save the enquiry, recommendation, and review in that order. The review is saved last to ensure
    # that incomplete bundles are not left in the pending queue.
    enquiry_id = _enquiry_filename(enquiry.enquiry_id)
    output_path = Path(output_dir)
    review_path = output_path / "reviews" / enquiry_id / f"{review.run_id}.json"

    if review_path.exists():
        raise FileExistsError("A review already exists for this run; use save_review to record a decision.")

    save_enquiry(enquiry, output_path)
    _atomic_save(recommendation, output_path / "recommendations" / f"{review.run_id}.json")
    save_review(review, output_path)

    return review

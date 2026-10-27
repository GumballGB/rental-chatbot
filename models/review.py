# Model for human review of rental enquiries and recommendations (HITL).

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from models.recommendation import Label


class Review(BaseModel):

    # Basic identifiers for the review
    enquiry_id: str
    run_id: UUID

    # The label recommended by the system for this enquiry
    recommended_label: Label
    # The duplicated enquiry id recommended by the system, if applicable
    recommended_duplicated_enquiry_id: str | None = None

    # Information about the human review
    reviewer: str | None = None
    review_date: datetime | None = None
    message: str | None = None

    # The final decision and label after human review
    decision: Literal["pending", "approved", "overridden"]
    final_label: Label | None = None

    # To confirm the duplicated enquiry in case of a duplicate final label
    final_duplicated_enquiry_id: str | None = None

    # Validator to ensure consistency between decision, final_label, and review information
    @model_validator(mode="after")
    def validate_review_state(self):
        if (
            self.recommended_label == "duplicate"
            and not self.recommended_duplicated_enquiry_id
        ):
            raise ValueError(
                "recommended_duplicated_enquiry_id is required when the "
                "recommended label is duplicate."
            )
        if (
            self.recommended_label != "duplicate"
            and self.recommended_duplicated_enquiry_id is not None
        ):
            raise ValueError(
                "recommended_duplicated_enquiry_id must be null unless the "
                "recommended label is duplicate."
            )
        if self.recommended_duplicated_enquiry_id == self.enquiry_id:
            raise ValueError("An enquiry cannot be a duplicate of itself.")

        if self.decision == "pending":
            if (
                self.final_label is not None
                or self.final_duplicated_enquiry_id is not None
            ):
                raise ValueError(
                    "final outcome must be null while review is pending."
                )
            if self.reviewer is not None or self.review_date is not None:
                raise ValueError(
                    "reviewer and review_date must be null while review is pending."
                )
            return self

        # For decided reviews, ensure that reviewer, review_date, and final_label are present
        if self.reviewer is None or self.review_date is None:
            raise ValueError(
                "reviewer and review_date are required for a decided review."
            )

        # Ensure that final_label is present for decided reviews
        if self.final_label is None:
            raise ValueError("final_label is required for a decided review.")
        if self.final_label == "duplicate" and not self.final_duplicated_enquiry_id:
            raise ValueError(
                "final_duplicated_enquiry_id is required when the final label "
                "is duplicate."
            )
        if (
            self.final_label != "duplicate"
            and self.final_duplicated_enquiry_id is not None
        ):
            raise ValueError(
                "final_duplicated_enquiry_id must be null unless the final "
                "label is duplicate."
            )
        if self.final_duplicated_enquiry_id == self.enquiry_id:
            raise ValueError("An enquiry cannot be a duplicate of itself.")

        recommended_outcome = (
            self.recommended_label,
            self.recommended_duplicated_enquiry_id,
        )
        final_outcome = (
            self.final_label,
            self.final_duplicated_enquiry_id,
        )

        # Ensure that approved reviews preserve the complete recommendation outcome
        if self.decision == "approved" and final_outcome != recommended_outcome:
            raise ValueError(
                "final outcome must equal recommended outcome when review is approved."
            )

        # Ensure that overridden reviews explain and change the complete outcome
        if self.decision == "overridden" and not self.message:
            raise ValueError("message is required when review is overridden.")
        if self.decision == "overridden" and final_outcome == recommended_outcome:
            raise ValueError(
                "final outcome must differ from recommended outcome when review "
                "is overridden."
            )

        return self

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

    # Information about the human review
    reviewer: str | None = None
    review_date: datetime | None = None
    message: str | None = None

    # The final decision and label after human review
    decision: Literal["pending", "approved", "overridden"]
    final_label: Label | None = None

    # Validator to ensure consistency between decision, final_label, and review information
    @model_validator(mode="after")
    def validate_review_state(self):
        if self.decision == "pending":
            if self.final_label is not None:
                raise ValueError("final_label must be null while review is pending.")
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

        # Ensure that approved reviews have final_label equal to recommended_label
        if (
            self.decision == "approved"
            and self.final_label != self.recommended_label
        ):
            raise ValueError(
                "final_label must equal recommended_label when review is approved."
            )

        # Ensure that overridden reviews have a message and final_label differs from recommended_label
        if self.decision == "overridden" and not self.message:
            raise ValueError("message is required when review is overridden.")
        if (
            self.decision == "overridden"
            and self.final_label == self.recommended_label
        ):
            raise ValueError(
                "final_label must differ from recommended_label when review is overridden."
            )

        return self

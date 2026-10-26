# For the agent triage part

from typing import Literal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator


class Evidence(BaseModel):
    source: Literal["message", "tool_result"]
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8)]
    support: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Recommendation(BaseModel):

    referred_enquiry_id: str
    duplicated_enquiry_id: str | None = None
    label: Literal["genuine", "needs_info", "spam", "duplicate"]
    reason: str
    evidence: list[Evidence] = Field(min_length=1, max_length=5)

    # A duplicate enquiry id is required if the label is considered to be a duplicate
    @model_validator(mode="after")
    def validate_duplicate_fields(self):
        
        if self.label == "duplicate" and not self.duplicated_enquiry_id:
            raise ValueError(
                "duplicated_enquiry_id is required when label is duplicate."
            )
        if self.label != "duplicate" and self.duplicated_enquiry_id is not None:
            raise ValueError(
                "duplicated_enquiry_id must be null unless label is duplicate."
            )
        return self

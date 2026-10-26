# Model for capturing events for the agent triage part.

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from models.recommendation import Recommendation


class Event(BaseModel):

    run_id: UUID
    enquiry_id: str

    time: datetime
    model: str | None = None

    # Depending on the type of event, the fields may be subject to change.
    type: Literal[
        "run_started",
        "tool_call",
        "tool_result",
        "model_call",
        "recommendation",
        "guard_result",
        "run_finished",
    ]

    tool: str | None = None

    # Specific to model_call events
    tokens_in: int | None = Field(default=None, ge=0)
    tokens_out: int | None = Field(default=None, ge=0)

    # Specific to recommendation events
    recommendation: Recommendation | None = None

    # Specific to guard_result events
    guard: str | None = None
    guard_passed: bool | None = None
    guard_result_reason: str | None = None

    # Specific to tool_call / tool_result events
    args: dict[str, Any] | None = None
    tool_succeeded: bool | None = None
    tool_result: str | None = None

    # Specific to run_finished events
    run_succeeded: bool | None = None
    final_label: Literal["genuine", "needs_info", "spam", "duplicate"] | None = None

    @model_validator(mode="after")
    def validate_type_specific_fields(self):

        if self.type == "run_started":

            if self.model is None:
                raise ValueError("model is required for run_started events.")

        # If it is a model_call event, ensure that model, tokens_in, and tokens_out are present
        if self.type == "model_call":

            if self.model is None:
                raise ValueError("model is required for model_call events.")
            if self.tokens_in is None or self.tokens_out is None:
                raise ValueError("tokens_in and tokens_out are required for model_call events.")

        # If it is a tool_call event, ensure that tool and args are present
        if self.type == "tool_call":

            if self.tool is None:
                raise ValueError("tool is required for tool_call events.")
            if self.args is None:
                raise ValueError("args is required for tool_call events.")

        if self.type == "tool_result":

            if self.tool is None:
                raise ValueError("tool is required for tool_result events.")
            if self.tool_succeeded is None:
                raise ValueError("tool_succeeded is required for tool_result events.")
            if self.tool_result is None:
                raise ValueError("tool_result is required for tool_result events.")

        # If it is a guard_result event, ensure that guard, guard_passed, and guard_result_reason are present
        if self.type == "guard_result":

            if self.guard is None:
                raise ValueError("guard is required for guard_result events.")
            if self.guard_passed is None:
                raise ValueError("guard_passed is required for guard_result events.")
            if self.guard_result_reason is None:
                raise ValueError("guard_result_reason is required for guard_result events.")

        if self.type == "recommendation":

            if self.recommendation is None:
                raise ValueError("recommendation is required for recommendation events.")

        if self.type == "run_finished":
            
            if self.run_succeeded is None:
                raise ValueError("run_succeeded is required for run_finished events.")
            if self.run_succeeded and self.final_label is None:
                raise ValueError("final_label is required for run_finished events.")

        return self
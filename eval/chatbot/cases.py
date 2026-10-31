# Load fixed conversations and their separate final-result answer key.

import json
from datetime import date
from pathlib import Path

from models.unit_enquiry import UnitEnquiry

SCORED_FIELDS = ("name", "email", "phone", "move_in_date", "budget", "listing_id")
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def index_records(records: list[dict], kind: str) -> dict:
    indexed = {}
    for record in records:
        conversation_id = record.get("conversation_id") if isinstance(record, dict) else None
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError(f"A nonblank {kind} conversation_id is required.")
        if conversation_id in indexed:
            raise ValueError(f"Duplicate {kind} conversation_id: {conversation_id}")
        indexed[conversation_id] = record
    return indexed


def validate_answers(answers: list[dict]) -> dict:
    """Validate the answer key for the benchmark."""

    indexed = index_records(answers, "expected")

    # Validate each answer's expected fields and declined_fields.
    for conversation_id, answer in indexed.items():
        expected = answer.get("expected")

        if not isinstance(expected, dict) or set(expected) != {*SCORED_FIELDS, "declined_fields"}:
            raise ValueError(f"{conversation_id}: expected must contain the six scored fields and declined_fields.")
        UnitEnquiry.model_validate(expected)

        if expected["move_in_date"] is not None:
            date.fromisoformat(expected["move_in_date"])

        if expected["budget"] is not None and type(expected["budget"]) is not int:
            raise ValueError(f"{conversation_id}: expected budget must be an integer or null.")
        
        declined = expected["declined_fields"]

        if not isinstance(declined, list) or any(field not in SCORED_FIELDS for field in declined):
            raise ValueError(f"{conversation_id}: declined_fields must list scored field names.")
        
        if len(set(declined)) != len(declined):
            raise ValueError(f"{conversation_id}: repeated declined field.")
        
        if any(expected[field] is not None for field in declined):
            raise ValueError(f"{conversation_id}: a declined field must have a null expected value.")
    return indexed


def load_cases(data_dir: str | Path = DEFAULT_DATA_DIR) -> tuple[list[dict], list[dict]]:
    """Validate the complete benchmark before any model call or runtime write."""

    # Load the conversations and answer key, then validate them.
    data_dir = Path(data_dir)
    conversations = json.loads((data_dir / "conversations.json").read_text(encoding="utf-8"))
    answers = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    by_id = index_records(conversations, "input")
    expected = validate_answers(answers)

    # Validate that every conversation has a corresponding answer and vice versa.
    if not by_id or set(by_id) != set(expected):
        raise ValueError("The answer key must cover every conversation exactly once.")

    # Validate each conversation's messages.
    for conversation_id, conversation in by_id.items():
        messages = conversation.get("messages")
        if not isinstance(messages, list) or len(messages) < 3 or len(messages) % 2 != 1:
            raise ValueError(f"{conversation_id}: expected user/assistant turns ending in user done.")
        for index, message in enumerate(messages):
            role = "user" if index % 2 == 0 else "assistant"
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                raise ValueError(f"{conversation_id}: messages need only role and content.")
            if message["role"] != role or not isinstance(message["content"], str) or not message["content"].strip():
                raise ValueError(f"{conversation_id}: messages must alternate nonblank user and assistant text.")
            if role == "user" and message["content"].strip().lower() == "done" and index != len(messages) - 1:
                raise ValueError(f"{conversation_id}: done must end the conversation.")
        if messages[-1]["content"].strip().lower() != "done":
            raise ValueError(f"{conversation_id}: conversation must end in done.")
    return conversations, answers


def extraction_messages(conversation: dict) -> list[dict]:
    """Match the app: consume done locally, then request one final extraction."""
    return [
        *(message.copy() for message in conversation["messages"][:-1]),
        {"role": "user", "content": "Extract the rental enquiry from this conversation."},
    ]

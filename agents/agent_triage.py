from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from uuid import uuid4

from agents.anthropic_functions import MODEL, parse_model_json, run_tool_loop
from core.audit import DEFAULT_AUDIT_DIR, write_event
from core.evidence import find_evidence_failures
from models.enquiry import Enquiry
from models.event import Event
from models.recommendation import Recommendation

TRIAGE_SYSTEM_PROMPT = """
You triage rental enquiries into one of these labels:
genuine, needs_info, spam, or duplicate.

Use tools when they can verify claims about listings, buildings, or locations.
Return only a JSON object matching these fields:
referred_enquiry_id, duplicated_enquiry_id, label, reason, evidence.

Rules:
- referred_enquiry_id must exactly match the supplied enquiry_id.
- duplicated_enquiry_id must be null unless the label is duplicate.
- Include between one and five evidence items.
- Every evidence quote must be an exact quote from either the enquiry message
  or a tool result.
- Evidence source must be either "message" or "tool_result".
- Never invent evidence or facts.
- Return valid JSON without markdown fences or extra text.
"""

# Helper function to write audit events for this run
def audit_event(triage_run_id, enquiry, audit_dir, event_type, **details):

    # Write the event to the audit log
    write_event(
        Event(
            run_id=triage_run_id,
            enquiry_id=enquiry.enquiry_id,
            time=datetime.now(UTC),
            type=event_type,
            **details,
        ),
        audit_dir=audit_dir,
    )

# Helper function to help save a tool for evidence checking
def handle_loop_event(
    triage_run_id,
    enquiry,
    audit_dir,
    tool_results,
    event_type,
    **details,
):
    if event_type == "tool_result":
        tool_results.append(details["tool_result"])

    audit_event(triage_run_id, enquiry, audit_dir, event_type, **details)

# Big function to triage a rental enquiry into a recommendation, it first runs the
# tool loop to gather information and then validates the evidence before returning a recommendation.
def triage_enquiry(
    enquiry: Enquiry,
    client,
    data_store,
    audit_dir: str | Path = DEFAULT_AUDIT_DIR,
) -> Recommendation:
    """
    Triage a rental enquiry into a recommendation. This function runs a tool loop to gather 
    additional information for triage, validates the evidence, and returns a Recommendation object.
    
    The returned Recommendation object contains the final label, reason, and evidence
    for the triage decision.
    
    Parameters:
        enquiry (Enquiry): The rental enquiry to be triaged.
        client: The client used to run the tool loop.
        data_store: The data store used to fetch additional information.
        audit_dir (str | Path, optional): Directory to store audit logs. Defaults to DEFAULT_AUDIT_DIR.

    Returns:
        Recommendation: The final recommendation for the triage decision.
    """

    # An event ID for this run, note runs are only for triage events.
    triage_run_id = uuid4()

    # Since we are starting the run, initialize the event fields
    tool_results = []
    run_succeeded = False
    final_label = None

    loop_event_handler = partial(
        handle_loop_event,
        triage_run_id,
        enquiry,
        audit_dir,
        tool_results,
    )

    # Audit the start of the triage run (EVENT)
    audit_event(triage_run_id, enquiry, audit_dir, "run_started", model=MODEL)

    try:

        # -*-*- RECOMMENDATION PHASE -*-*-

        # STEP 1: Prepare the initial messages for the tool loop with the enquiry details
        # This builds the request for the tool loop with the enquiry details
        messages = [
            {
                "role": "user",
                "content": (
                    "Triage this rental enquiry:\n"
                    f"{enquiry.model_dump_json()}" # Convert pydantic into json
                ),
            }
        ]

        # STEP 2: Run the tool loop with the prepared messages to gather additional information for triage.
        # Examples are for duplicate detection, spam detection.
        response_text, _ = run_tool_loop(
            messages,
            client,
            data_store,
            system=TRIAGE_SYSTEM_PROMPT,
            on_event=loop_event_handler,
        )

        # STEP 3: Validate the response from the tool loop as a Recommendation object
        # The response_text from the tool loop is expected to be a JSON representation of a 
        # Recommendation object
        recommendation = Recommendation.model_validate(
            parse_model_json(response_text)
        )

        # Audit the recommendation for this triage run (EVENT)
        audit_event(
            triage_run_id,
            enquiry,
            audit_dir,
            "recommendation",
            recommendation=recommendation,
        )

        # -*-*- EVIDENCE CHECK PHASE -*-*-

        # Check for any evidence failures in the recommendation against the enquiry and tool results
        failures = find_evidence_failures(
            recommendation,
            enquiry.message or "",
            tool_results,
        )

        guard_passed = not failures

        guard_reason = (
            "All evidence quotes were found in their declared sources."
            if guard_passed
            else "; ".join(
                f"evidence[{failure.index}] {failure.reason}"
                for failure in failures
            )
        )

        # Audit the evidence check result for this triage run (EVENT)
        audit_event(
            triage_run_id,
            enquiry,
            audit_dir,
            "guard_result",
            guard="evidence_check",
            guard_passed=guard_passed,
            guard_result_reason=guard_reason,
        )

        # Check if the evidence check passed before proceeding with the final recommendation
        if not guard_passed:
            raise ValueError(f"Recommendation failed evidence check: {guard_reason}")

        final_label = recommendation.label
        run_succeeded = True
        return recommendation

    # Audit the final decision for this triage run (EVENT)
    finally:
        audit_event(
            triage_run_id,
            enquiry,
            audit_dir,
            "run_finished",
            run_succeeded=run_succeeded,
            final_label=final_label,
        )


import argparse
from pathlib import Path

import dotenv

from agents.agent_triage import triage_enquiry
from agents.anthropic_functions import boot_anthropic
from agents.rental_chatbot import run_rental_chat

from core.audit import DEFAULT_AUDIT_DIR
from core.manual_review import run_manual_review
from core.store import JsonStore
from core.writer import DEFAULT_OUTPUT_DIR

from models.triage_result import TriageResult

# Entry point for the rental chatbot application.
def run_application(
    client,
    data_store,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    audit_dir: str | Path = DEFAULT_AUDIT_DIR,
    review: bool = True,
) -> TriageResult:
    """Collect and save an enquiry, triage it, then hand it to human review."""
    
    # Run the rental chat to collect the enquiry and any declined fields.
    enquiry, declined_fields = run_rental_chat(client, data_store, output_dir=output_dir)

    # Save the enquiry to the output directory.
    enquiry_path = Path(output_dir) / "enquiries" / f"{enquiry.enquiry_id}.json"
    print(f"Saved enquiry {enquiry.enquiry_id} to {enquiry_path}")
    print({"declined_fields": sorted(declined_fields)})

    print("Running triage...")
    
    # Attempt to triage the enquiry using the AI agent.
    try:
        result = triage_enquiry(
            enquiry, client, data_store, audit_dir=audit_dir, output_dir=output_dir,
        )
    except Exception:
        print(
            f"Triage failed for {enquiry.enquiry_id}. "
            f"The enquiry is saved at {enquiry_path}. Check {audit_dir} for run details."
        )
        raise

    # Print the recommended label and queue for human review.
    print(f"Recommended label: {result.recommendation.label} (run {result.run_id})")
    print("Queued for human review; the final decision is pending.")

    # If human review is enabled, prompt for the reviewer name 
    # and run the manual review process.
    if review:
        try:
            reviewer = input("Reviewer name [admin]: ").strip() or "admin"
        except (EOFError, KeyboardInterrupt):
            return result
        run_manual_review(output_dir=output_dir, reviewer=reviewer, ask=input, show=print)
    else:
        print("Run python -m core.manual_review to approve or override pending recommendations.")

    return result


def main(argv: list[str] | None = None) -> None:

    parser = argparse.ArgumentParser(description="Collect and triage a rental enquiry, then review it.")
    parser.add_argument("--queue-only", action="store_true", help="Queue triage without opening human review.")
    args = parser.parse_args(argv)
    
    dotenv.load_dotenv()
    
    client = boot_anthropic()
    data_store = JsonStore()

    # Run the application, optionally skipping human review if --queue-only is specified.
    run_application(client, data_store, review=not args.queue_only)


if __name__ == "__main__":
    main()

# Run triage evaluation and save each attempt separately under output/eval/.

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from anthropic import AnthropicError
from dotenv import load_dotenv

from agents.agent_triage import triage_enquiry
from agents.anthropic_functions import MODEL, boot_anthropic
from core.store import DATA_DIR, JsonStore
from core.writer import DEFAULT_OUTPUT_DIR
from eval.metrics import calculate_metrics
from eval.report import render_metrics

DEFAULT_EVAL_DIR = DEFAULT_OUTPUT_DIR / "eval"


def _save_json(path: Path, contents) -> None:

    path.write_text(
        json.dumps(contents, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run_evaluation(
    client,
    data_dir: str | Path = DATA_DIR,
    output_dir: str | Path = DEFAULT_EVAL_DIR,
    *,
    limit: int | None = None,
    ids: list[str] | None = None,
    show=print,
) -> Path:
    """
    Evaluate original triage recommendations and return the saved run folder.

    The answer key must cover every enquiry exactly once, even when limit or ids
    selects a smaller evaluation. ids preserves the requested order and cannot
    be combined with limit. All enquiries remain available to the read-only
    store for earlier duplicate context. Expected answers never enter triage
    requests.

    Parse, guard, tool-loop and API errors become failed predictions, and the
    next case continues. Filesystem errors and keyboard interrupts propagate.
    Completed predictions are saved after each case. Evaluation creates no
    pending reviews; its audit logs live inside this evaluation's own folder.
    """

    # Guard the limit argument before loading the answer key, to avoid wasting API calls or creating output files.
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive.")
    if ids is not None:
        if limit is not None:
            raise ValueError("ids and limit cannot be combined.")
        if not ids or any(not isinstance(value, str) or not value.strip() for value in ids):
            raise ValueError("IDs must be a non-empty list of nonblank enquiry IDs.")
        ids = [value.strip() for value in ids]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs must not contain repeated enquiry IDs.")
    
    data_dir = Path(data_dir)
    expected_answers = json.loads(
        (data_dir / "enquiry_recommendation_ground_truth.json").read_text(encoding="utf-8")
    )

    # Validate the key before spending API calls or creating output files.
    calculate_metrics(expected_answers, [])
    store = JsonStore(data_dir)

    if {answer["enquiry_id"] for answer in expected_answers} != set(store.enquiries):
        raise ValueError("The answer key must cover every input enquiry exactly once.")
    if ids is not None:
        answers_by_id = {answer["enquiry_id"]: answer for answer in expected_answers}
        unknown_ids = set(ids) - answers_by_id.keys()
        if unknown_ids:
            raise ValueError(f"Unknown enquiry IDs: {', '.join(sorted(unknown_ids))}")
        expected_answers = [answers_by_id[enquiry_id] for enquiry_id in ids]
    elif limit is not None:
        expected_answers = expected_answers[:limit]

    started_at = datetime.now(UTC).isoformat()
    run_dir = Path(output_dir) / str(uuid4())
    run_dir.mkdir(parents=True)

    _save_json(run_dir / "expected_answers.json", expected_answers)
    
    predictions = []
    _save_json(run_dir / "predictions.json", predictions)

    # Evaluate each expected answer in order, saving the predictions after each case.
    for index, answer in enumerate(expected_answers, start=1):
        enquiry_id = answer["enquiry_id"]
        audit_path = Path("audit") / f"{index:04d}"
        prediction = {
            "enquiry_id": enquiry_id,
            "run_id": None,
            "predicted_label": None,
            "predicted_duplicated_enquiry_id": None,
            "recommendation": None,
            "error": None,
            "audit_dir": audit_path.as_posix(),
        }

    # -*-*- TRIAGE PHASE -*-*- #

        try:
            result = triage_enquiry(
                store.get_enquiry(enquiry_id), client, store,
                audit_dir=run_dir / audit_path, output_dir=None,
            )
        except (ValueError, RuntimeError, AnthropicError) as error:
            prediction["error"] = f"{type(error).__name__}: {error}"
        else:
            recommendation = result.recommendation
            prediction.update(
                run_id=str(result.run_id),
                predicted_label=recommendation.label,
                predicted_duplicated_enquiry_id=recommendation.duplicated_enquiry_id,
                recommendation=recommendation.model_dump(mode="json"),
            )
        predictions.append(prediction)
        _save_json(run_dir / "predictions.json", predictions)
        label = prediction["predicted_label"] or "no recommendation"
        show(f"[{index}/{len(expected_answers)}] {enquiry_id}: {label}")

    # -*-*- METRICS PHASE -*-*- #

    metrics = calculate_metrics(expected_answers, predictions)

    # Save the metrics and report to the run folder, and show a summary to the user.
    metrics["metadata"] = {
        "model": MODEL,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "data_dir": str(data_dir.resolve()),
    }

    # Save the metrics and report to the run folder, and show a summary to the user.
    _save_json(run_dir / "metrics.json", metrics)
    report_text = render_metrics(metrics)
    (run_dir / "report.txt").write_text(report_text + "\n", encoding="utf-8")
    show(report_text)
    show(f"Evaluation saved to {run_dir}")
    return run_dir

def _parse_ids(value: str) -> list[str]:
    """Read a comma-separated CLI list without silently dropping empty entries."""
    ids = [enquiry_id.strip() for enquiry_id in value.split(",")]
    if not all(ids):
        raise argparse.ArgumentTypeError("--ids needs nonblank, comma-separated enquiry IDs")
    return ids


# The Main Function #
def main(argv: list[str] | None = None) -> None:
    """Read command-line options and start an evaluation with the real client."""

    # Parse command-line arguments, load environment variables, and run the evaluation.
    parser = argparse.ArgumentParser(description="Evaluate triage on fictional enquiries.")
    parser.add_argument("--data-dir", type=Path, default=Path(DATA_DIR))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EVAL_DIR)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--limit", type=int, help="Evaluate only the first N answer-key cases.")
    selection.add_argument("--ids", type=_parse_ids, help="Comma-separated enquiry IDs, in evaluation order.")
    args = parser.parse_args(argv)

    # Guard the limit argument before loading the answer key, to avoid wasting API calls or creating output files.
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    # Load ANTHROPIC key
    load_dotenv()

    # Run the evaluation with the real client, saving results to a new folder under output/eval/.
    run_evaluation(
        boot_anthropic(), data_dir=args.data_dir, output_dir=args.output_dir,
        limit=args.limit, ids=args.ids,
    )


if __name__ == "__main__":
    main()

# Evaluate one final extraction per fixed transcript, with no live turn loop.

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from anthropic import AnthropicError
from dotenv import load_dotenv

from agents.anthropic_functions import (
    EXTRACTION_MAX_TOKENS,
    MODEL,
    boot_anthropic,
    extract_enquiry_unit_enquiry,
)
from core.writer import DEFAULT_OUTPUT_DIR
from eval.chatbot.cases import DEFAULT_DATA_DIR, extraction_messages, load_cases
from eval.chatbot.metrics import calculate_metrics
from eval.chatbot.report import render_metrics

DEFAULT_EVAL_DIR = DEFAULT_OUTPUT_DIR / "eval" / "chatbot"


def _save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_evaluation(
    client, data_dir: str | Path = DEFAULT_DATA_DIR, output_dir: str | Path = DEFAULT_EVAL_DIR,
    *, limit: int | None = None, show=print,
) -> Path:
    """Use the production extractor once per transcript and compare final fields.

    done is consumed locally, as in run_rental_chat. Expected answers and case
    titles never reach the model. No runtime enquiries or reviews are created.
    Failed calls stay in the report, without automatic retries.
    """
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive.")
    conversations, answers = load_cases(data_dir)
    if limit is not None:
        conversations = conversations[:limit]
    selected = {case["conversation_id"] for case in conversations}
    answers = [answer for answer in answers if answer["conversation_id"] in selected]
    started_at = datetime.now(UTC).isoformat()
    run_dir = Path(output_dir) / str(uuid4())
    run_dir.mkdir(parents=True)
    _save_json(run_dir / "conversations.json", conversations)
    _save_json(run_dir / "expected_answers.json", answers)
    predictions = []
    _save_json(run_dir / "predictions.json", predictions)
    for index, case in enumerate(conversations, start=1):
        prediction = {"conversation_id": case["conversation_id"], "extracted": None, "error": None}
        try:
            enquiry, declined = extract_enquiry_unit_enquiry(extraction_messages(case), client)
            prediction["extracted"] = {**enquiry.model_dump(mode="json"), "declined_fields": sorted(declined)}
        except (ValueError, TypeError, RuntimeError, AnthropicError) as error:
            prediction["error"] = f"{type(error).__name__}: {error}"
        predictions.append(prediction)
        _save_json(run_dir / "predictions.json", predictions)
        status = "extracted" if not prediction["error"] else "failed"
        show(f"[{index}/{len(conversations)}] {case['conversation_id']}: {status}")

    metrics = calculate_metrics(answers, predictions)
    metrics["metadata"] = {
        "model": MODEL, "stage": "final_extraction", "max_tokens": EXTRACTION_MAX_TOKENS,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(), "data_dir": str(Path(data_dir).resolve()),
    }
    _save_json(run_dir / "metrics.json", metrics)
    text = render_metrics(metrics)
    (run_dir / "report.txt").write_text(text + "\n", encoding="utf-8")
    show(text)
    show(f"Evaluation saved to {run_dir}")
    return run_dir


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate final extraction from fixed fictional conversations.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--limit", type=int, help="Evaluate only the first N conversations.")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    load_dotenv()
    run_evaluation(boot_anthropic(), args.data_dir, args.output_dir, limit=args.limit)


if __name__ == "__main__":
    main()

"""Estimate recorded API token costs; the CLI never calls a model."""

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Standard, uncached Claude API rates in USD per million tokens.
# Keep the source/date with the rates so saved estimates are reproducible.
HAIKU_PRICING = {
    "model": "claude-haiku-5-5",
    "input_per_million": 0.10,
    "output_per_million": 0.50,
    "long_context_threshold": 100_000,
    "long_input_per_million": 0.50,
    "long_output_per_million": 2.50,
    "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    "checked_on": "2026-10-31",
}


def estimate_cost(
    input_tokens: int, output_tokens: int,
    input_price_per_million: float, output_price_per_million: float,
) -> float:
    """Calculate USD from supplied rates, keeping fractions of a cent."""

    # Validate the inputs to avoid nonsensical calculations.
    for count in (input_tokens, output_tokens):
        if type(count) is not int or count < 0:
            raise ValueError("Token counts must be non-negative integers.")
    
    rates = []

    for rate in (input_price_per_million, output_price_per_million):
        try:
            value = Decimal(str(rate))
        except InvalidOperation as error:
            raise ValueError("Prices must be finite, non-negative numbers.") from error
        if not value.is_finite() or value < 0:
            raise ValueError("Prices must be finite, non-negative numbers.")
        rates.append(value)
    return float((input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000)


def summarize_cost(calls: list[dict], total_cases: int, *, warnings=()) -> dict:
    """
    Price each recorded response, including tool turns and rejected outputs.

    Unknown models or incomplete usage make the full estimate unavailable.
    recorded_cost_usd remains the subtotal of the calls that could be priced.
    Caching is not enabled by these evaluators; recorded cache usage is flagged
    rather than incorrectly applying uncached rates.
    """

    # Validate the total_cases argument to ensure it's a non-negative integer.
    if type(total_cases) is not int or total_cases < 0:
        raise ValueError("The case count must be a non-negative integer.")
    
    warnings = list(warnings)
    subtotal = Decimal(0)
    tokens_in = tokens_out = priced_calls = 0
    
    # Iterate through each call to calculate costs and handle any issues.
    for index, call in enumerate(calls, start=1):
        try:
            incoming, outgoing = call["tokens_in"], call["tokens_out"]
            estimate_cost(incoming, outgoing, 0, 0)
        except (KeyError, ValueError, TypeError):
            warnings.append(f"Call {index}: invalid or missing token counts.")
            continue
        tokens_in += incoming
        tokens_out += outgoing
        if call.get("model") != HAIKU_PRICING["model"]:
            warnings.append(f"Call {index}: no saved pricing for model {call.get('model')!r}.")
            continue
        if call.get("cache_read_input_tokens") or call.get("cache_creation_input_tokens"):
            warnings.append(f"Call {index}: cache token pricing is not supported by this estimator.")
            continue
        long_context = incoming > HAIKU_PRICING["long_context_threshold"]
        prefix = "long_" if long_context else ""
        amount = estimate_cost(
            incoming, outgoing,
            HAIKU_PRICING[prefix + "input_per_million"],
            HAIKU_PRICING[prefix + "output_per_million"],
        )
        subtotal += Decimal(str(amount))
        priced_calls += 1
    
    if not calls:
        warnings.append("No model response usage was recorded; cost is unavailable, not zero.")
    
    complete = not warnings

    # Return a structured summary of the cost estimation, including warnings and pricing details.
    return {
        "currency": "USD", "cases": total_cases, "model_calls": len(calls),
        "priced_calls": priced_calls, "input_tokens": tokens_in, "output_tokens": tokens_out,
        "estimated_cost_usd": float(subtotal) if complete else None,
        "recorded_cost_usd": float(subtotal),
        "average_cost_per_case_usd": float(subtotal / total_cases) if complete and total_cases else None,
        "pricing": [dict(HAIKU_PRICING)] if priced_calls else [],
        "warnings": warnings,
        "scope": (
            "Standard uncached API response tokens, including failed cases. "
            "Excludes discounts, taxes and retries or requests with no recorded response. "
            "Older audit logs do not record cache counters; uncached requests are assumed."
        ),
    }


def triage_cost(run_dir: str | Path, predictions: list[dict]) -> dict:
    """Read only the audit folders linked by these predictions, once each."""
    
    # Validate the run_dir argument to ensure it's a valid path.
    run_dir = Path(run_dir).resolve()
    calls, warnings = [], []
    seen = set()
    
    # Iterate through each prediction to process 
    # its associated audit logs and calculate costs.
    for prediction in predictions:
        case_id = prediction["enquiry_id"]
        try:
            relative = prediction.get("audit_dir")
            if not isinstance(relative, str) or not relative:
                raise ValueError("audit_dir is missing")
            folder = (run_dir / relative).resolve()
            if not folder.is_relative_to(run_dir) or folder in seen:
                raise ValueError("audit_dir is outside this run or used more than once")
            seen.add(folder)
            logs = sorted(folder.glob("*.jsonl"))
            if not logs:
                raise ValueError("audit log missing")
            case_calls = []
            for path in logs:
                if not path.resolve().is_relative_to(run_dir):
                    raise ValueError("audit log is outside this run")
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("audit event must be an object")
                        if event.get("type") == "model_call":
                            case_calls.append(event)
            if not case_calls:
                raise ValueError("no model response usage recorded (request may have failed before responding)")
            calls.extend(case_calls)
        except (OSError, ValueError) as error:
            warnings.append(f"{case_id}: {error}")
    return summarize_cost(calls, len(predictions), warnings=warnings)


def saved_run_cost(run_dir: str | Path) -> dict:
    """Recover costs for a completed evaluation, leaving original files intact."""

    run_dir = Path(run_dir)
    if not (run_dir / "metrics.json").is_file():
        raise ValueError("Choose a completed evaluation with metrics.json; let running evaluations finish.")
    
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    predictions = json.loads((run_dir / "predictions.json").read_text(encoding="utf-8"))
    
    if len(predictions) != metrics["total"]:
        raise ValueError("Prediction count does not match the completed evaluation's total.")
    
    if metrics.get("metadata", {}).get("stage") != "final_extraction":
        return triage_cost(run_dir, predictions)
    usage_path = run_dir / "usage.json"
    
    if not usage_path.is_file():
        return summarize_cost([], len(predictions), warnings=["usage.json missing; older extraction runs did not save usage."])
    calls = json.loads(usage_path.read_text(encoding="utf-8"))
    
    return chatbot_cost(calls, predictions)


def chatbot_cost(calls: list[dict], predictions: list[dict]) -> dict:
    """Flag cases without responses rather than treating API failures as free."""

    expected_ids = {prediction["conversation_id"] for prediction in predictions}
    covered = {call.get("conversation_id") for call in calls}
    
    warnings = [
        f"{prediction['conversation_id']}: no model response usage recorded."
        for prediction in predictions if prediction["conversation_id"] not in covered
    ]
    
    if covered - expected_ids:
        warnings.append("Usage contains conversation IDs outside this evaluation.")
    return summarize_cost(calls, len(predictions), warnings=warnings)


def render_cost(cost: dict) -> str:
    """Format the estimate and its limits for either evaluation's report."""

    amount = cost["estimated_cost_usd"]
    average = cost["average_cost_per_case_usd"]
    lines = [
        f"Token usage: {cost['input_tokens']:,} input / {cost['output_tokens']:,} output; {cost['model_calls']} model calls",
        f"Estimated token cost (USD): ${amount:.6f}" if amount is not None else "Estimated token cost (USD): unavailable (incomplete usage or pricing)",
        f"Average per case, including failures (USD): ${average:.8f}" if average is not None else "Average per case (USD): unavailable",
    ]
    
    if cost["warnings"]:
        lines.append(f"Priced recorded calls only (USD): ${cost['recorded_cost_usd']:.6f}")
        lines.extend("Warning: " + warning for warning in cost["warnings"])
    for pricing in cost["pricing"]:
        lines.append(
            f"{pricing['model']}: ${pricing['input_per_million']:.2f} input / "
            f"${pricing['output_per_million']:.2f} output per million tokens; prompts over "
            f"{pricing['long_context_threshold']:,}: ${pricing['long_input_per_million']:.2f} / "
            f"${pricing['long_output_per_million']:.2f}. Checked {pricing['checked_on']}."
        )
        lines.append("Pricing source: " + pricing["source"])
    lines.append(cost["scope"])
    return "\n".join(lines)


def save_cost_report(run_dir: str | Path, cost: dict) -> None:
    """Save derived sidecars without rewriting predictions, metrics or audits."""
    
    run_dir = Path(run_dir)
    (run_dir / "cost.json").write_text(json.dumps(cost, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (run_dir / "cost_report.txt").write_text(render_cost(cost) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Estimate a saved evaluation's token costs; no API calls.")
    parser.add_argument("run_dir", type=Path, help="Completed evaluation folder containing metrics.json and usage logs.")
    args = parser.parse_args(argv)
   
    try:
        cost = saved_run_cost(args.run_dir)
        save_cost_report(args.run_dir, cost)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(render_cost(cost))
    print(f"Cost estimate saved to {args.run_dir / 'cost.json'}")


if __name__ == "__main__":
    main()

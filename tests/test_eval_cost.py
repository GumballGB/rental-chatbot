# Check dollar calculations and recovering usage without another model call.

import json
from copy import deepcopy

import pytest

from eval.cost import estimate_cost, main, saved_run_cost, summarize_cost


def call(tokens_in, tokens_out, model="claude-haiku-5-5"):
    return {"model": model, "tokens_in": tokens_in, "tokens_out": tokens_out}


def test_estimate_uses_the_supplied_rates_without_rounding_to_cents():
    assert estimate_cost(1000, 500, 0.10, 0.50) == pytest.approx(0.00035)
    assert estimate_cost(1000, 500, 2, 10) == pytest.approx(0.007)
    assert estimate_cost(0, 0, 0.10, 0.50) == 0


@pytest.mark.parametrize("values", [
    (-1, 0, 0.1, 0.5), (0, -1, 0.1, 0.5), (True, 0, 0.1, 0.5),
    (1.5, 0, 0.1, 0.5), (0, 0, -0.1, 0.5), (0, 0, 0.1, float("nan")),
    (0, 0, float("inf"), 0.5),
    (0, 0, "invalid", 0.5), (0, 0, True, 0.5),
])
def test_bad_counts_and_rates_are_rejected(values):
    with pytest.raises(ValueError):
        estimate_cost(*values)


def test_tool_turns_are_summed_and_the_context_tier_applies_per_call():
    calls = [call(60000, 100), call(60000, 100), call(100001, 100)]
    original = deepcopy(calls)

    cost = summarize_cost(calls, total_cases=2)

    # Two short prompts use .10/.50; only the third uses .50/2.50.
    assert cost["estimated_cost_usd"] == pytest.approx(0.0623505)
    assert cost["average_cost_per_case_usd"] == pytest.approx(0.03117525)
    assert cost["input_tokens"] == 220001
    assert cost["output_tokens"] == 300
    assert cost["model_calls"] == 3
    assert cost["pricing"][0]["source"].startswith("https://platform.claude.com/")
    assert cost["pricing"][0]["checked_on"]
    assert calls == original
    json.dumps(cost, allow_nan=False)


def test_unknown_model_does_not_get_haiku_prices_or_a_false_zero_total():
    cost = summarize_cost([call(1000, 500), call(2000, 100, model="unknown")], 2)
    assert cost["estimated_cost_usd"] is None
    assert cost["average_cost_per_case_usd"] is None
    assert cost["recorded_cost_usd"] == pytest.approx(0.00035)
    assert cost["input_tokens"] == 3000
    assert "unknown" in " ".join(cost["warnings"])


def test_missing_usage_is_unavailable_rather_than_free():
    cost = summarize_cost([], 1)
    assert cost["estimated_cost_usd"] is None
    assert cost["average_cost_per_case_usd"] is None
    assert cost["warnings"]


def test_recorded_cache_tokens_are_not_silently_priced_as_uncached():
    cost = summarize_cost([{**call(1000, 500), "cache_read_input_tokens": 4000}], 1)
    assert cost["estimated_cost_usd"] is None
    assert "cache" in " ".join(cost["warnings"]).lower()


@pytest.fixture
def completed_run(tmp_path):
    (tmp_path / "metrics.json").write_text(json.dumps({"total": 2}), encoding="utf-8")
    predictions = [
        {"enquiry_id": "ENQ-1", "audit_dir": "audit/0001", "error": None},
        {"enquiry_id": "ENQ-2", "audit_dir": "audit/0002", "error": "truncated"},
    ]
    (tmp_path / "predictions.json").write_text(json.dumps(predictions), encoding="utf-8")
    (tmp_path / "report.txt").write_text("Original classification report\n", encoding="utf-8")
    for index, entries in enumerate(([call(1000, 500), call(2000, 300)], [call(1000, 1024)]), start=1):
        folder = tmp_path / "audit" / f"{index:04d}"
        folder.mkdir(parents=True)
        # Non-model events must not be charged again.
        events = [{"type": "tool_result"}, *[{"type": "model_call", **entry} for entry in entries]]
        (folder / "run.jsonl").write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
    return tmp_path


def test_backfill_includes_failed_cases_and_preserves_original_outputs(completed_run):
    original = {path: path.read_bytes() for path in completed_run.rglob("*") if path.is_file()}

    main([str(completed_run)])

    cost = json.loads((completed_run / "cost.json").read_text(encoding="utf-8"))
    assert cost["estimated_cost_usd"] == pytest.approx(0.001312)
    assert cost["average_cost_per_case_usd"] == pytest.approx(0.000656)
    assert cost["model_calls"] == 3
    assert cost["cases"] == 2
    assert not cost["warnings"]
    assert "Estimated token cost (USD): $0.001312" in (completed_run / "cost_report.txt").read_text(encoding="utf-8")
    assert original == {path: path.read_bytes() for path in original}


@pytest.mark.parametrize("problem", ["missing", "corrupt", "no_model_calls"])
def test_incomplete_audit_logs_are_reported_without_claiming_a_full_cost(completed_run, problem):
    log = completed_run / "audit/0002/run.jsonl"
    if problem == "missing":
        log.unlink()
    else:
        log.write_text("broken JSON" if problem == "corrupt" else '{"type": "run_started"}', encoding="utf-8")
    cost = saved_run_cost(completed_run)
    assert cost["estimated_cost_usd"] is None
    assert cost["recorded_cost_usd"] == pytest.approx(0.0007)
    assert "ENQ-2" in " ".join(cost["warnings"])


def test_running_eval_is_not_treated_as_completed(completed_run):
    (completed_run / "metrics.json").unlink()
    with pytest.raises(ValueError, match="completed"):
        saved_run_cost(completed_run)
    assert not (completed_run / "cost.json").exists()


def test_old_chatbot_run_without_usage_cannot_be_recovered(completed_run):
    (completed_run / "metrics.json").write_text(json.dumps({
        "total": 2, "metadata": {"stage": "final_extraction"},
    }), encoding="utf-8")
    cost = saved_run_cost(completed_run)
    assert cost["estimated_cost_usd"] is None
    assert "usage.json" in " ".join(cost["warnings"])


def test_backfill_cannot_read_audits_outside_the_run(completed_run):
    path = completed_run / "predictions.json"
    predictions = json.loads(path.read_text(encoding="utf-8"))
    predictions[1]["audit_dir"] = "../outside"
    path.write_text(json.dumps(predictions), encoding="utf-8")
    cost = saved_run_cost(completed_run)
    assert cost["estimated_cost_usd"] is None
    assert "outside" in " ".join(cost["warnings"])

"""Exercise evaluation with real triage code and scripted model responses."""

import json

import pytest

from eval.run_eval import main, run_evaluation
from tests.fakes import FakeAnthropicClient, text_response, tool_use_response


@pytest.fixture
def eval_data(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for filename in ("buildings.json", "listings.json", "locations.json"):
        (data_dir / filename).write_text("[]", encoding="utf-8")
    enquiries = [
        {
            "enquiry_id": f"ENQ-{index:03d}",
            "name": f"Renter {index}",
            "email": f"renter{index}@example.com",
            "message": "I am looking for a rental apartment.",
            "received_date": f"2026-10-{19 + index}",
        }
        for index in range(1, 4)
    ]
    answers = [
        {"enquiry_id": enquiry["enquiry_id"], "expected_label": label,
         "rationale": "ANSWER KEY ONLY: never send this rationale to the model."}
        for enquiry, label in zip(enquiries, ("genuine", "needs_info", "spam"))
    ]
    (data_dir / "unit_enquiries.json").write_text(json.dumps(enquiries), encoding="utf-8")
    (data_dir / "enquiry_recommendation_ground_truth.json").write_text(
        json.dumps(answers), encoding="utf-8"
    )
    return data_dir


def recommendation_response(enquiry_id, label="genuine", *, quote="looking for a rental apartment", target=None):
    return text_response(json.dumps({
        "referred_enquiry_id": enquiry_id,
        "label": label,
        "duplicated_enquiry_id": target,
        "reason": "A scripted classification for testing the runner.",
        "evidence": [{"source": "message", "quote": quote, "support": "Quotes the message."}],
    }))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_evaluation_records_success_failure_and_continues_without_creating_reviews(eval_data, tmp_path):
    original_files = {path.name: path.read_bytes() for path in eval_data.iterdir()}
    client = FakeAnthropicClient([
        recommendation_response("ENQ-001"),
        recommendation_response("ENQ-002", "needs_info", quote="This quote was invented."),
        recommendation_response("ENQ-003", "spam"),
    ])
    shown = []

    run_dir = run_evaluation(
        client, data_dir=eval_data, output_dir=tmp_path / "eval", show=shown.append
    )

    assert run_dir.parent == tmp_path / "eval"
    predictions = read_json(run_dir / "predictions.json")
    assert [row["predicted_label"] for row in predictions] == ["genuine", None, "spam"]
    assert "failed evidence check" in predictions[1]["error"]
    assert predictions[0]["recommendation"]["evidence"][0]["quote"] == "looking for a rental apartment"
    for prediction in predictions:
        audit_files = list((run_dir / prediction["audit_dir"]).glob("*.jsonl"))
        assert len(audit_files) == 1
    assert predictions[0]["run_id"] == next((run_dir / predictions[0]["audit_dir"]).glob("*.jsonl")).stem
    metrics = read_json(run_dir / "metrics.json")
    assert metrics["total"] == 3
    assert metrics["correct"] == 2
    assert metrics["failed"] == 1
    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert metrics["metadata"]["model"]
    assert read_json(run_dir / "expected_answers.json") == read_json(
        eval_data / "enquiry_recommendation_ground_truth.json"
    )
    assert "Confusion matrix" in (run_dir / "report.txt").read_text(encoding="utf-8")
    assert any("ENQ-003" in line for line in shown)
    assert any("Failed runs: 1/3" in line for line in shown)
    assert not list(run_dir.rglob("reviews"))
    assert not list(run_dir.rglob("enquiries"))
    assert original_files == {path.name: path.read_bytes() for path in eval_data.iterdir()}
    assert "ANSWER KEY ONLY" not in json.dumps(client.messages.calls)


@pytest.mark.parametrize("selection", [{"limit": 1}, {"ids": ["ENQ-003"]}])
def test_selection_scores_a_subset_but_duplicate_tools_keep_the_full_store(eval_data, tmp_path, selection):
    enquiries = read_json(eval_data / "unit_enquiries.json")
    enquiries[2]["email"] = enquiries[0]["email"]
    (eval_data / "unit_enquiries.json").write_text(json.dumps(enquiries), encoding="utf-8")
    answers = read_json(eval_data / "enquiry_recommendation_ground_truth.json")
    answers[2].update(expected_label="duplicate", expected_duplicated_enquiry_id="ENQ-001")
    (eval_data / "enquiry_recommendation_ground_truth.json").write_text(
        json.dumps(list(reversed(answers))), encoding="utf-8"
    )
    client = FakeAnthropicClient([
        tool_use_response("find_duplicate_enquiry_candidates", {}),
        recommendation_response("ENQ-003", "duplicate", target="ENQ-001"),
    ])

    run_dir = run_evaluation(client, eval_data, tmp_path / "eval", show=lambda _: None, **selection)

    metrics = read_json(run_dir / "metrics.json")
    assert metrics["total"] == 1
    assert metrics["duplicate_outcomes"] == {"correct": 1, "total": 1, "accuracy": 1.0}
    tool_result = client.messages.calls[1]["messages"][-1]["content"][0]["content"]
    assert "ENQ-001" in tool_result
    assert len(read_json(run_dir / "expected_answers.json")) == 1


def test_ids_select_only_requested_cases_in_the_requested_order(eval_data, tmp_path):
    client = FakeAnthropicClient([
        recommendation_response("ENQ-003", "spam"),
        recommendation_response("ENQ-001"),
    ])

    run_dir = run_evaluation(
        client, eval_data, tmp_path / "eval", ids=["ENQ-003", "ENQ-001"], show=lambda _: None,
    )

    expected_ids = ["ENQ-003", "ENQ-001"]
    assert [row["enquiry_id"] for row in read_json(run_dir / "predictions.json")] == expected_ids
    assert [row["enquiry_id"] for row in read_json(run_dir / "expected_answers.json")] == expected_ids
    assert len(client.messages.calls) == 2
    assert read_json(run_dir / "metrics.json")["correct"] == 2


@pytest.mark.parametrize("ids", [[], ["UNKNOWN"], ["ENQ-001", "ENQ-001"], [""]])
def test_invalid_ids_fail_before_requests_or_output_writes(eval_data, tmp_path, ids):
    client = FakeAnthropicClient([])

    with pytest.raises(ValueError, match="IDs"):
        run_evaluation(client, eval_data, tmp_path / "eval", ids=ids, show=lambda _: None)

    assert client.messages.calls == []
    assert not (tmp_path / "eval").exists()


def test_ids_and_limit_cannot_be_combined(eval_data, tmp_path):
    client = FakeAnthropicClient([])
    with pytest.raises(ValueError, match="ids and limit"):
        run_evaluation(client, eval_data, tmp_path / "eval", ids=["ENQ-001"], limit=1)
    assert client.messages.calls == []
    assert not (tmp_path / "eval").exists()


def test_repeated_evaluations_keep_previous_outputs(eval_data, tmp_path):
    def run_once():
        client = FakeAnthropicClient([recommendation_response("ENQ-001")])
        return run_evaluation(client, eval_data, tmp_path / "eval", limit=1, show=lambda _: None)

    first = run_once()
    first_files = {path.relative_to(first): path.read_bytes() for path in first.rglob("*") if path.is_file()}
    second = run_once()

    assert first != second
    assert first_files == {path.relative_to(first): path.read_bytes() for path in first.rglob("*") if path.is_file()}


@pytest.mark.parametrize("problem", ["missing_answer", "unknown_enquiry", "duplicate_answer", "invalid_label"])
def test_bad_answer_keys_fail_before_model_calls_or_output_writes(eval_data, tmp_path, problem):
    path = eval_data / "enquiry_recommendation_ground_truth.json"
    answers = read_json(path)
    if problem == "missing_answer":
        answers.pop()
    elif problem == "unknown_enquiry":
        answers[0]["enquiry_id"] = "UNKNOWN"
    elif problem == "duplicate_answer":
        answers.append(answers[0])
    else:
        answers[0]["expected_label"] = "typo"
    path.write_text(json.dumps(answers), encoding="utf-8")
    client = FakeAnthropicClient([])

    with pytest.raises(ValueError):
        run_evaluation(client, eval_data, tmp_path / "eval", show=lambda _: None)

    assert client.messages.calls == []
    assert not (tmp_path / "eval").exists()


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_limit_is_rejected_before_model_calls(eval_data, tmp_path, limit):
    client = FakeAnthropicClient([])
    with pytest.raises(ValueError, match="limit must be positive"):
        run_evaluation(client, eval_data, tmp_path / "eval", limit=limit)
    assert client.messages.calls == []


def test_filesystem_errors_are_not_scored_as_model_failures(eval_data, tmp_path, monkeypatch):
    def cannot_write(*args, **kwargs):
        raise OSError("Disk full")

    monkeypatch.setattr("eval.run_eval.triage_enquiry", cannot_write)
    with pytest.raises(OSError, match="Disk full"):
        run_evaluation(FakeAnthropicClient([]), eval_data, tmp_path / "eval", show=lambda _: None)


def test_cli_uses_given_directories_and_limit(eval_data, tmp_path, monkeypatch):
    client = FakeAnthropicClient([recommendation_response("ENQ-001")])
    monkeypatch.setattr("eval.run_eval.boot_anthropic", lambda: client)
    monkeypatch.setattr("eval.run_eval.load_dotenv", lambda: None)

    main(["--data-dir", str(eval_data), "--output-dir", str(tmp_path / "eval"), "--limit", "1"])

    reports = list((tmp_path / "eval").glob("*/report.txt"))
    assert len(reports) == 1
    assert "Label accuracy: 1/1" in reports[0].read_text(encoding="utf-8")


def test_cli_accepts_comma_separated_ids_and_trims_spaces(eval_data, tmp_path, monkeypatch):
    client = FakeAnthropicClient([
        recommendation_response("ENQ-003", "spam"), recommendation_response("ENQ-001"),
    ])
    monkeypatch.setattr("eval.run_eval.boot_anthropic", lambda: client)
    monkeypatch.setattr("eval.run_eval.load_dotenv", lambda: None)

    main([
        "--data-dir", str(eval_data), "--output-dir", str(tmp_path / "eval"),
        "--ids", " ENQ-003, ENQ-001 ",
    ])

    predictions_path = next((tmp_path / "eval").glob("*/predictions.json"))
    assert [row["enquiry_id"] for row in read_json(predictions_path)] == ["ENQ-003", "ENQ-001"]


@pytest.mark.parametrize("selection", [
    ["--ids", ""], ["--ids", "ENQ-001,,ENQ-003"],
    ["--limit", "1", "--ids", "ENQ-001"],
])
def test_invalid_cli_selection_exits_before_creating_a_client(selection, monkeypatch):
    def unexpected_client():
        pytest.fail("Invalid selection must fail before creating a client.")

    monkeypatch.setattr("eval.run_eval.boot_anthropic", unexpected_client)
    with pytest.raises(SystemExit) as error:
        main(selection)
    assert error.value.code == 2

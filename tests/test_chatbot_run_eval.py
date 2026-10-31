# Only the final extraction is invoked and scored for each fixed transcript

import json
from copy import deepcopy

import pytest

from agents.anthropic_functions import EXTRACTION_MAX_TOKENS
from core.store import JsonStore
from eval.chatbot.cases import DEFAULT_DATA_DIR, extraction_messages, load_cases
from eval.chatbot.run_eval import main, run_evaluation
from tests.fakes import FakeAnthropicClient, text_response


@pytest.fixture
def cases_dir(tmp_path):
    data_dir = tmp_path / "cases"
    data_dir.mkdir()
    for filename in ("conversations.json", "ground_truth.json"):
        (data_dir / filename).write_bytes((DEFAULT_DATA_DIR / filename).read_bytes())
    return data_dir


def response_for(answer):
    return text_response(json.dumps({**answer["expected"], "message": "A fictional rental request."}, ensure_ascii=False))


def test_ten_cases_include_immediate_done_five_turns_and_declines():
    conversations, answers = load_cases()
    counts = [(len(case["messages"]) - 1) // 2 for case in conversations]
    store = JsonStore()

    assert len(conversations) == len(answers) == 10
    assert counts[:2] == [1, 1]
    assert min(counts) == 1 and max(counts) == 5
    assert counts.count(5) >= 3
    assert any(answer["expected"]["declined_fields"] for answer in answers)
    for answer in answers:
        listing = answer["expected"]["listing_id"]
        if listing:
            assert store.get_listing(listing)


def test_extracts_once_per_full_transcript_without_sending_done_or_answers(cases_dir, tmp_path):
    conversations, answers = load_cases(cases_dir)
    original_files = {path.name: path.read_bytes() for path in cases_dir.iterdir()}
    # An answer-key-only marker must never enter model requests.
    key_path = cases_dir / "ground_truth.json"
    for answer in answers:
        answer["notes"] = "EXPECTED ANSWERS ONLY"
    key_path.write_text(json.dumps(answers), encoding="utf-8")
    client = FakeAnthropicClient([response_for(answer) for answer in answers])

    run_dir = run_evaluation(client, cases_dir, tmp_path / "output", show=lambda _: None)

    assert len(client.messages.calls) == 10
    for call, conversation in zip(client.messages.calls, conversations):
        assert call["messages"] == extraction_messages(conversation)
        assert all(message["content"].strip().lower() != "done" for message in call["messages"])
        assert call["max_tokens"] == EXTRACTION_MAX_TOKENS
        assert "EXPECTED ANSWERS ONLY" not in json.dumps(call)
        assert conversation["title"] not in json.dumps(call)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["correct"] == metrics["total"] == 10
    assert metrics["failed"] == 0
    assert metrics["metadata"]["max_tokens"] == EXTRACTION_MAX_TOKENS
    assert "Whole result correct: 10/10" in (run_dir / "report.txt").read_text(encoding="utf-8")
    assert not list(run_dir.rglob("reviews"))
    assert not list(run_dir.rglob("enquiries"))
    assert (cases_dir / "conversations.json").read_bytes() == original_files["conversations.json"]
    assert json.loads(key_path.read_text(encoding="utf-8")) == answers


def test_failed_extraction_is_saved_and_the_next_case_runs(cases_dir, tmp_path):
    _, answers = load_cases(cases_dir)
    client = FakeAnthropicClient([
        text_response("partial", stop_reason="max_tokens"), response_for(answers[1]),
    ])

    run_dir = run_evaluation(client, cases_dir, tmp_path / "output", limit=2, show=lambda _: None)

    report = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert report["total"] == 2
    assert report["correct"] == report["failed"] == 1
    assert report["accuracy"] == 0.5
    assert "max_tokens" in report["failures"][0]["error"]
    assert len(client.messages.calls) == 2


@pytest.mark.parametrize("problem", ["duplicate", "missing_answer", "unknown_field", "declined_value", "early_done", "no_done", "bad_role"])
def test_invalid_fixtures_fail_before_model_calls_and_output_writes(cases_dir, tmp_path, problem):
    conversations, answers = load_cases(cases_dir)
    if problem == "duplicate":
        conversations.append(deepcopy(conversations[0]))
    elif problem == "missing_answer":
        answers.pop()
    elif problem == "unknown_field":
        answers[0]["expected"]["surprise"] = "not scored"
    elif problem == "declined_value":
        answers[0]["expected"]["declined_fields"] = ["phone"]
    elif problem == "early_done":
        conversations[0]["messages"][0]["content"] = "done"
    elif problem == "no_done":
        conversations[0]["messages"][-1]["content"] = "more details"
    else:
        conversations[0]["messages"][0]["role"] = "system"
    for filename, contents in (("conversations.json", conversations), ("ground_truth.json", answers)):
        (cases_dir / filename).write_text(json.dumps(contents), encoding="utf-8")
    client = FakeAnthropicClient([])

    with pytest.raises(ValueError):
        run_evaluation(client, cases_dir, tmp_path / "output", show=lambda _: None)

    assert client.messages.calls == []
    assert not (tmp_path / "output").exists()


def test_building_extraction_messages_does_not_mutate_transcript():
    conversations, _ = load_cases()
    before = deepcopy(conversations[0])

    messages = extraction_messages(conversations[0])
    messages[0]["content"] = "Changed in the request only."

    assert conversations[0] == before


def test_cli_uses_the_fake_client_and_selected_limit(cases_dir, tmp_path, monkeypatch):
    _, answers = load_cases(cases_dir)
    client = FakeAnthropicClient([response_for(answers[0])])
    monkeypatch.setattr("eval.chatbot.run_eval.boot_anthropic", lambda: client)
    monkeypatch.setattr("eval.chatbot.run_eval.load_dotenv", lambda: None)

    main(["--data-dir", str(cases_dir), "--output-dir", str(tmp_path / "output"), "--limit", "1"])

    assert len(client.messages.calls) == 1
    assert len(list((tmp_path / "output").glob("*/report.txt"))) == 1


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_limit_is_rejected_before_model_calls(cases_dir, tmp_path, limit):
    client = FakeAnthropicClient([])

    with pytest.raises(ValueError, match="limit must be positive"):
        run_evaluation(client, cases_dir, tmp_path / "output", limit=limit)

    assert not (tmp_path / "output").exists()

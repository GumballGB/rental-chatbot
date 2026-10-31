# Hand-counted final fields verify scoring independently of a live model.

import json
from copy import deepcopy

import pytest

from eval.chatbot.metrics import calculate_metrics
from eval.chatbot.report import render_metrics


def expected(conversation_id, **values):
    fields = {"name": None, "email": None, "phone": None, "move_in_date": None,
              "budget": None, "listing_id": None, "declined_fields": []}
    fields.update(values)
    return {"conversation_id": conversation_id, "expected": fields}


def prediction(answer, **changes):
    fields = deepcopy(answer["expected"])
    fields.update(changes)
    return {"conversation_id": answer["conversation_id"], "extracted": fields, "error": None}


def test_field_counts_show_omissions_invented_values_wrong_values_and_failures():
    answers = [expected(f"C{index}", name="Sam", budget=1900) for index in range(1, 5)]
    predictions = [
        prediction(answers[0]),
        prediction(answers[1], name=None, budget=2000, phone="+1-514-555-0201"),
        prediction(answers[2], name="Jo"),
    ]

    report = calculate_metrics(answers, list(reversed(predictions)))

    assert report["total"] == 4
    assert report["correct"] == 1
    assert report["accuracy"] == 0.25
    assert report["failed"] == 1
    assert report["per_field"]["name"] == {
        "correct": 1, "correct_values": 1, "expected_values": 4,
        "invented": 0, "omitted": 1, "wrong": 1,
        "accuracy": 0.25, "supplied_accuracy": 0.25, "failed": 1,
    }
    phone = report["per_field"]["phone"]
    assert phone["correct"] == 2
    assert phone["invented"] == 1
    assert phone["expected_values"] == 0
    assert phone["supplied_accuracy"] is None
    assert report["per_field"]["budget"]["wrong"] == 1
    assert report["declined_fields"]["correct"] == 3
    assert report["failures"] == [{"conversation_id": "C4", "error": "No extraction recorded."}]


def test_normalization_allows_formatting_but_preserves_names_accents_and_ids():
    answer = expected("C1", name="Amélie", email="sam@example.com", phone="+1-514-555-0201", listing_id="LST-037")
    result = prediction(answer, name=" Ame\u0301lie ", email="SAM@EXAMPLE.COM", phone="(514) 555-0201", message="A differently worded summary.")

    assert calculate_metrics([answer], [result])["correct"] == 1
    for changes in ({"name": "Amelie"}, {"name": "amélie"}, {"listing_id": "lst-037"}):
        assert calculate_metrics([answer], [prediction(answer, **changes)])["correct"] == 0


def test_declined_fields_are_compared_as_a_final_set():
    answer = expected("C1", declined_fields=["phone", "budget"])

    assert calculate_metrics([answer], [prediction(answer, declined_fields=["budget", "phone"])])["correct"] == 1
    report = calculate_metrics([answer], [prediction(answer, declined_fields=[])])
    assert report["correct"] == 0
    assert report["declined_fields"]["correct"] == 0
    assert "declined_fields" in report["cases"][0]["mismatches"]


def test_error_overrides_a_partial_extraction_and_stays_in_denominators():
    answer = expected("C1", name="Sam")
    result = prediction(answer)
    result["error"] = "Extraction did not finish: max_tokens"

    report = calculate_metrics([answer], [result])

    assert report["failed"] == 1
    assert report["accuracy"] == 0.0
    assert report["per_field"]["name"]["supplied_accuracy"] == 0.0
    assert report["declined_fields"]["accuracy"] == 0.0


def test_empty_scores_are_undefined_and_report_is_serializable_without_input_mutation():
    answers = [expected("C1", name="Sam")]
    predictions = [prediction(answers[0])]
    before = deepcopy((answers, predictions))

    report = calculate_metrics(answers, predictions)

    assert json.loads(json.dumps(report)) == report
    assert (answers, predictions) == before
    assert calculate_metrics([], [])["accuracy"] is None
    assert "n/a" in render_metrics(calculate_metrics([], []))


@pytest.mark.parametrize("problem", ["duplicate_expected", "duplicate_prediction", "unknown_prediction"])
def test_ambiguous_case_ids_are_rejected(problem):
    answers = [expected("C1")]
    predictions = [prediction(answers[0])]
    if problem == "duplicate_expected":
        answers *= 2
    elif problem == "duplicate_prediction":
        predictions *= 2
    else:
        predictions[0]["conversation_id"] = "UNKNOWN"

    with pytest.raises(ValueError):
        calculate_metrics(answers, predictions)


def test_report_shows_counts_refusals_and_specific_final_field_errors(monkeypatch):
    answer = expected("C1", name="Sam", budget=2000, declined_fields=["phone"])
    report = calculate_metrics([answer], [prediction(answer, budget=1800, declined_fields=[])])
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: pytest.fail("Rendering must return text."))

    text = render_metrics(report)

    assert "Whole result correct: 0/1" in text
    assert "Supplied correct" in text
    assert "Invented" in text and "Omitted" in text
    assert "Declined fields exact match: 0/1" in text
    assert "budget: expected 2000, got 1800" in text

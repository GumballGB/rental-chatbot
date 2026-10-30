# Hand-counted results verify scoring independently of any model.

import json
from copy import deepcopy

import pytest

from eval.metrics import calculate_metrics
from eval.report import render_metrics


@pytest.fixture
def example_results():
    expected = [
        {"enquiry_id": "E1", "expected_label": "genuine"},
        {"enquiry_id": "E2", "expected_label": "genuine"},
        {"enquiry_id": "E3", "expected_label": "needs_info"},
        {"enquiry_id": "E4", "expected_label": "needs_info"},
        {"enquiry_id": "E5", "expected_label": "spam"},
        {"enquiry_id": "E6", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "OLD-A"},
        {"enquiry_id": "E7", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "OLD-C"},
        {"enquiry_id": "E8", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "OLD-D"},
        {"enquiry_id": "E9", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "OLD-E"},
    ]
    # Reverse order deliberately: matching must use IDs, not list positions.
    predictions = [
        {"enquiry_id": "E8", "predicted_label": "genuine"},
        {"enquiry_id": "E7", "predicted_label": "duplicate", "predicted_duplicated_enquiry_id": "OLD-C"},
        {"enquiry_id": "E6", "predicted_label": "duplicate", "predicted_duplicated_enquiry_id": "OLD-B"},
        {"enquiry_id": "E5", "predicted_label": "spam"},
        {"enquiry_id": "E4", "predicted_label": None, "error": "Evidence guard rejected quote."},
        {"enquiry_id": "E3", "predicted_label": "genuine"},
        {"enquiry_id": "E2", "predicted_label": "spam"},
        {"enquiry_id": "E1", "predicted_label": "genuine"},
    ]
    return expected, predictions


def test_confusion_matrix_uses_expected_rows_and_counts_every_case(example_results):
    report = calculate_metrics(*example_results)

    assert report["confusion_matrix"] == {
        "genuine": {"genuine": 1, "needs_info": 0, "spam": 1, "duplicate": 0, "no recommendation": 0},
        "needs_info": {"genuine": 1, "needs_info": 0, "spam": 0, "duplicate": 0, "no recommendation": 1},
        "spam": {"genuine": 0, "needs_info": 0, "spam": 1, "duplicate": 0, "no recommendation": 0},
        "duplicate": {"genuine": 1, "needs_info": 0, "spam": 0, "duplicate": 2, "no recommendation": 1},
    }
    assert sum(sum(row.values()) for row in report["confusion_matrix"].values()) == 9


def test_per_class_counts_precision_and_recall_are_hand_calculated(example_results):
    report = calculate_metrics(*example_results)
    genuine = report["per_class"]["genuine"]

    assert genuine["support"] == 2
    assert genuine["predicted"] == 3
    assert genuine["true_positive"] == 1
    assert genuine["false_positive"] == 2
    assert genuine["false_negative"] == 1
    assert genuine["precision"] == pytest.approx(1 / 3)
    assert genuine["recall"] == 0.5
    assert report["per_class"]["spam"]["precision"] == 0.5
    assert report["per_class"]["spam"]["recall"] == 1.0
    assert report["per_class"]["needs_info"]["precision"] is None
    assert report["per_class"]["needs_info"]["recall"] == 0.0
    assert report["per_class"]["duplicate"]["recall"] == 0.5


def test_failures_and_missing_results_reduce_accuracy_and_recall(example_results):
    report = calculate_metrics(*example_results)

    assert report["total"] == 9
    assert report["correct"] == 4
    assert report["accuracy"] == pytest.approx(4 / 9)
    assert report["failed"] == 2
    assert report["failures"] == [
        {"enquiry_id": "E4", "error": "Evidence guard rejected quote."},
        {"enquiry_id": "E9", "error": "No prediction recorded."},
    ]


def test_duplicate_target_scoring_includes_wrong_labels_and_failed_runs(example_results):
    report = calculate_metrics(*example_results)

    # Two duplicate labels are correct, but only one complete outcome is correct.
    assert report["per_class"]["duplicate"]["true_positive"] == 2
    assert report["duplicate_outcomes"] == {"correct": 1, "total": 4, "accuracy": 0.25}


@pytest.mark.parametrize("target", ["WRONG", None, "E1"])
def test_correct_duplicate_label_with_wrong_or_missing_target_is_not_exact(target):
    expected = [{"enquiry_id": "E1", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "OLD"}]
    predictions = [{"enquiry_id": "E1", "predicted_label": "duplicate", "predicted_duplicated_enquiry_id": target}]

    report = calculate_metrics(expected, predictions)

    assert report["accuracy"] == 1.0
    assert report["duplicate_outcomes"] == {"correct": 0, "total": 1, "accuracy": 0.0}


def test_duplicate_reference_can_be_outside_the_evaluated_subset():
    expected = [{"enquiry_id": "E1", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "OLD"}]
    predictions = [{"enquiry_id": "E1", "predicted_label": "duplicate", "predicted_duplicated_enquiry_id": "OLD"}]

    assert calculate_metrics(expected, predictions)["duplicate_outcomes"]["accuracy"] == 1.0


@pytest.mark.parametrize("partial_label", ["genuine", "invalid_label", None])
def test_guard_or_parse_error_counts_as_failure_even_with_a_partial_label(partial_label):
    expected = [{"enquiry_id": "E1", "expected_label": "genuine"}]
    predictions = [{"enquiry_id": "E1", "predicted_label": partial_label, "error": "Run failed."}]

    report = calculate_metrics(expected, predictions)

    assert report["failed"] == 1
    assert report["accuracy"] == 0.0
    assert report["confusion_matrix"]["genuine"]["no recommendation"] == 1
    assert report["per_class"]["genuine"]["recall"] == 0.0


def test_no_recommendation_without_an_error_has_a_default_explanation():
    expected = [{"enquiry_id": "E1", "expected_label": "genuine"}]

    report = calculate_metrics(expected, [{"enquiry_id": "E1", "predicted_label": None}])

    assert report["failures"] == [{"enquiry_id": "E1", "error": "No recommendation returned."}]


def test_empty_evaluation_has_undefined_rates_and_zero_counts():
    report = calculate_metrics([], [])

    assert report["total"] == report["correct"] == report["failed"] == 0
    assert report["accuracy"] is None
    assert report["duplicate_outcomes"] == {"correct": 0, "total": 0, "accuracy": None}
    for stats in report["per_class"].values():
        assert stats["support"] == stats["predicted"] == 0
        assert stats["precision"] is stats["recall"] is None
    assert "n/a" in render_metrics(report)


def test_prediction_of_an_absent_class_has_zero_precision_and_undefined_recall():
    report = calculate_metrics(
        [{"enquiry_id": "E1", "expected_label": "genuine"}],
        [{"enquiry_id": "E1", "predicted_label": "spam"}],
    )

    spam = report["per_class"]["spam"]
    assert spam["support"] == 0
    assert spam["predicted"] == 1
    assert spam["precision"] == 0.0
    assert spam["recall"] is None


@pytest.mark.parametrize(("expected", "predictions", "error"), [
    ([{"enquiry_id": "E1", "expected_label": "genuine"}] * 2, [], "Duplicate expected enquiry_id"),
    ([{"enquiry_id": "E1", "expected_label": "genuine"}], [{"enquiry_id": "E1", "predicted_label": "genuine"}] * 2, "Duplicate prediction enquiry_id"),
    ([{"enquiry_id": "E1", "expected_label": "genuine"}], [{"enquiry_id": "OTHER", "predicted_label": "spam"}], "Unknown prediction enquiry_id"),
    ([{"enquiry_id": "E1", "expected_label": "typo"}], [], "Invalid expected label"),
    ([{"enquiry_id": "E1", "expected_label": "genuine"}], [{"enquiry_id": "E1", "predicted_label": "typo"}], "Invalid predicted label"),
    ([{"enquiry_id": "E1", "expected_label": "duplicate"}], [], "Expected duplicate target is required"),
    ([{"enquiry_id": "E1", "expected_label": "genuine", "expected_duplicated_enquiry_id": "OLD"}], [], "Expected duplicate target must be null"),
    ([{"enquiry_id": "E1", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "E1"}], [], "cannot refer to itself"),
    ([{"enquiry_id": "", "expected_label": "genuine"}], [], "expected enquiry_id"),
    ([{"enquiry_id": "E1", "expected_label": "genuine"}], [{"predicted_label": "spam"}], "prediction enquiry_id"),
])
def test_invalid_or_ambiguous_records_are_rejected(expected, predictions, error):
    with pytest.raises(ValueError, match=error):
        calculate_metrics(expected, predictions)


def test_report_is_json_serializable_and_inputs_are_not_changed(example_results):
    before = deepcopy(example_results)

    report = calculate_metrics(*example_results)

    assert json.loads(json.dumps(report)) == report
    assert example_results == before


def test_render_shows_matrix_class_counts_rates_duplicate_score_and_failures(example_results, monkeypatch):
    report = calculate_metrics(*example_results)

    def unexpected_print(*args, **kwargs):
        pytest.fail("Rendering should return text for the caller to display.")

    monkeypatch.setattr("builtins.print", unexpected_print)
    text = render_metrics(report)

    assert "Confusion matrix" in text
    assert "rows=expected" in text
    assert "columns=predicted" in text
    assert "no recommendation" in text
    assert "Support" in text and "Predicted" in text
    assert "Precision" in text and "Recall" in text
    assert "33.3%" in text and "50.0%" in text
    assert "n/a" in text
    assert "4/9" in text and "44.4%" in text
    assert "Duplicate exact outcomes: 1/4 (25.0%)" in text
    assert "Failed runs: 2/9" in text
    assert "E4: Evidence guard rejected quote." in text
    assert "E9: No prediction recorded." in text

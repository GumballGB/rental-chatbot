# Verify heatmap values and exported figures using saved metrics only. Generated

import json
from copy import deepcopy

import pytest

from eval.agent_triage.metrics import calculate_metrics
from eval.agent_triage.plot import main, plot_confusion_matrix


@pytest.fixture
def report():
    return calculate_metrics(
        [
            {"enquiry_id": "E1", "expected_label": "genuine"},
            {"enquiry_id": "E2", "expected_label": "genuine"},
            {"enquiry_id": "E3", "expected_label": "needs_info"},
            {"enquiry_id": "E4", "expected_label": "spam"},
            {"enquiry_id": "E5", "expected_label": "duplicate", "expected_duplicated_enquiry_id": "OLD"},
            {"enquiry_id": "E6", "expected_label": "needs_info"},
        ],
        [
            {"enquiry_id": "E1", "predicted_label": "genuine"},
            {"enquiry_id": "E2", "predicted_label": "spam"},
            {"enquiry_id": "E3", "predicted_label": None, "error": "Invalid evidence."},
            {"enquiry_id": "E4", "predicted_label": "spam"},
            {"enquiry_id": "E5", "predicted_label": "genuine"},
            {"enquiry_id": "E6", "predicted_label": "needs_info"},
        ],
    )


def test_heatmap_has_expected_rows_predicted_columns_and_failed_runs(report):
    figure = plot_confusion_matrix(report)
    axes = figure.axes[0]

    assert axes.images[0].get_array().tolist() == [
        [1, 0, 1, 0, 0],
        [0, 1, 0, 0, 1],
        [0, 0, 1, 0, 0],
        [1, 0, 0, 0, 0],
    ]
    assert axes.get_xlabel() == "Predicted label"
    assert axes.get_ylabel() == "Expected label"
    assert [tick.get_text().replace("\n", " ") for tick in axes.get_xticklabels()] == [
        "genuine", "needs_info", "spam", "duplicate", "no recommendation",
    ]
    assert "n=2" in axes.get_yticklabels()[1].get_text()
    assert "6 enquiries" in axes.get_title(loc="left")
    assert "1 failed" in axes.get_title(loc="left")
    assert axes.texts[9].get_text() == "1"


def test_normalized_heatmap_includes_failures_in_row_denominators(report):
    before = deepcopy(report)

    figure = plot_confusion_matrix(report, normalize=True)
    axes = figure.axes[0]

    assert axes.images[0].get_array().tolist() == [
        [0.5, 0.0, 0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0, 0.0, 0.5],
        [0.0, 0.0, 1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 0.0],
    ]
    assert axes.texts[6].get_text() == "50.0%"
    assert axes.texts[9].get_text() == "50.0%"
    assert report == before


def test_classes_with_no_examples_are_marked_undefined_when_normalized():
    report = calculate_metrics([{"enquiry_id": "E1", "expected_label": "genuine"}], [])

    figure = plot_confusion_matrix(report, normalize=True)
    axes = figure.axes[0]

    assert axes.texts[4].get_text() == "100.0%"
    assert sum(text.get_text() == "n/a" for text in axes.texts) == 15
    figure.canvas.draw()


def test_empty_evaluation_can_be_rendered_without_dividing_by_zero():
    figure = plot_confusion_matrix(calculate_metrics([], []), normalize=True)

    assert all(text.get_text() == "n/a" for text in figure.axes[0].texts)
    figure.canvas.draw()


@pytest.mark.parametrize("problem", ["missing_column", "negative_count", "fractional_count"])
def test_invalid_matrix_data_is_rejected(report, problem):
    if problem == "missing_column":
        del report["confusion_matrix"]["genuine"]["no recommendation"]
    else:
        report["confusion_matrix"]["genuine"]["spam"] = -1 if problem == "negative_count" else 0.5

    with pytest.raises(ValueError):
        plot_confusion_matrix(report)


def test_cli_saves_png_next_to_metrics_and_preserves_input(report, tmp_path):
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(report), encoding="utf-8")
    before = metrics_path.read_bytes()

    main([str(metrics_path)])

    assert (tmp_path / "confusion_matrix.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert metrics_path.read_bytes() == before


@pytest.mark.parametrize("extension", ["svg", "pdf"])
def test_cli_supports_normalized_vector_export(report, tmp_path, extension):
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(report), encoding="utf-8")
    output_path = tmp_path / "figures" / f"matrix.{extension}"

    main([str(metrics_path), "--normalize", "--output", str(output_path)])

    if extension == "svg":
        assert "<svg" in output_path.read_text(encoding="utf-8")
    else:
        assert output_path.read_bytes().startswith(b"%PDF")


def test_cli_does_not_overwrite_its_input(report, tmp_path):
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(report), encoding="utf-8")
    before = metrics_path.read_bytes()

    with pytest.raises(SystemExit) as error:
        main([str(metrics_path), "--output", str(metrics_path)])

    assert error.value.code == 2
    assert metrics_path.read_bytes() == before

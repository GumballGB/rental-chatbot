"""Render evaluation metrics as a readable text report."""

from eval.metrics import LABELS, NO_RECOMMENDATION


def _percentage(value: float | None) -> str:
    """Return a percentage string or n/a if the value is None."""

    if value is None:
        return "n/a"
    return f"{value:.1%}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    """Return a plain-text table with aligned columns."""

    widths = [max(len(row[i]) for row in [headers, *rows]) for i in range(len(headers))]

    # Render each row with cells left-justified to the column width, and join them with newlines.
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()
        for row in [headers, *rows]
    )


def render_metrics(report: dict) -> str:
    """Return a plain-text report for the caller to display or save."""

    columns = (*LABELS, NO_RECOMMENDATION)
    matrix_rows = [
        [label, *(str(report["confusion_matrix"][label][column]) for column in columns)]
        for label in LABELS
    ]

    class_rows = []

    # Render per-class metrics in a table format, including support, predicted counts, precision, 
    # and recall for each label.
    for label in LABELS:
        stats = report["per_class"][label]
        class_rows.append([
            label,
            str(stats["support"]),
            str(stats["predicted"]),
            _percentage(stats["precision"]),
            _percentage(stats["recall"]),
        ])

    duplicate = report["duplicate_outcomes"]

    sections = [
        f"Label accuracy: {report['correct']}/{report['total']} ({_percentage(report['accuracy'])})",
        "Confusion matrix (rows=expected, columns=predicted)\n"
        + _table(["Expected", *columns], matrix_rows),
        "Per-class metrics\n"
        + _table(["Label", "Support", "Predicted", "Precision", "Recall"], class_rows),
        (f"Duplicate exact outcomes: {duplicate['correct']}/{duplicate['total']} "
         f"({_percentage(duplicate['accuracy'])})"),
        f"Failed runs: {report['failed']}/{report['total']}",
    ]

    if report["failures"]:
        sections.append("\n".join(
            f"{failure['enquiry_id']}: {failure['error']}" for failure in report["failures"]
        ))

    return "\n\n".join(sections)

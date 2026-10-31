# Plot a completed evaluation's saved metrics without calling the model.

import argparse
import json
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator, PercentFormatter

from eval.agent_triage.metrics import LABELS, NO_RECOMMENDATION


def plot_confusion_matrix(report: dict, *, normalize: bool = False) -> Figure:
    """
    Return a heatmap figure with expected rows and predicted columns.

    Normalization divides each row by its support, including failed runs.
    Classes with no evaluated examples show n/a rather than a percentage.
    The caller can save the returned figure as PNG, PDF or SVG.
    """

    columns = (*LABELS, NO_RECOMMENDATION)

    try:
        counts = [[report["confusion_matrix"][label][column] for column in columns] for label in LABELS]

    except (KeyError, TypeError) as error:
        raise ValueError("Expected a confusion_matrix with every label and no recommendation column.") from error
    
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for row in counts for value in row):
        raise ValueError("Confusion-matrix counts must be non-negative integers.")

    supports = [sum(row) for row in counts]
    values = counts
    if normalize:
        values = [
            [value / support if support else 0.0 for value in row]
            for row, support in zip(counts, supports)
        ]

    maximum = 1 if normalize else max(1, max(value for row in counts for value in row))

    # Use a file-rendering canvas so exporting also works on Linux without a GUI.
    figure = Figure(figsize=(10, 6), layout="constrained", facecolor="white")
    FigureCanvasAgg(figure)
    axes = figure.subplots()

    image = axes.imshow(values, cmap="Blues", vmin=0, vmax=maximum, interpolation="nearest")
    axes.set_xticks(range(len(columns)), labels=[*LABELS, "no\nrecommendation"])
    axes.set_yticks(range(len(LABELS)), labels=[
        f"{label} (n={support})" for label, support in zip(LABELS, supports)
    ])
    axes.set_xlabel("Predicted label", labelpad=10)
    axes.set_ylabel("Expected label", labelpad=10)
    axes.set_title(
        f"Triage confusion matrix\n{sum(supports)} enquiries · {sum(row[-1] for row in counts)} failed runs",
        loc="left", pad=16, fontsize=14, fontweight="bold", color="#18344b",
    )
    axes.tick_params(length=0, labelsize=10)
    axes.set_xticks([index - 0.5 for index in range(len(columns) + 1)], minor=True)
    axes.set_yticks([index - 0.5 for index in range(len(LABELS) + 1)], minor=True)
    axes.grid(which="minor", color="white", linewidth=2)
    axes.tick_params(which="minor", bottom=False, left=False)
    for spine in axes.spines.values():
        spine.set_visible(False)

    for row, support in enumerate(supports):
        for column in range(len(columns)):
            value = values[row][column]
            if normalize:
                text = f"{value:.1%}" if support else "n/a"
            else:
                text = str(counts[row][column])
            axes.text(
                column, row, text, ha="center", va="center", fontsize=12,
                color="white" if value > maximum / 2 else "#18344b",
            )

    colorbar = figure.colorbar(image, ax=axes, shrink=0.85, pad=0.04)
    colorbar.set_label("Share of expected class" if normalize else "Enquiry count", labelpad=12)
    colorbar.outline.set_visible(False)
    if normalize:
        colorbar.ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    else:
        colorbar.ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    figure.supxlabel(
        "Percentages include failed runs. n/a = no examples for that class."
        if normalize else "Each cell counts enquiries; failed runs stay in the final column.",
        fontsize=9, color="#526575",
    )
    return figure


def main(argv: list[str] | None = None) -> None:
    """Read metrics.json and export a heatmap beside it or to --output."""

    parser = argparse.ArgumentParser(description="Plot saved triage evaluation metrics; no model calls.")
    parser.add_argument("metrics_path", type=Path, help="Path to a completed evaluation's metrics.json.")
    parser.add_argument("--normalize", action="store_true", help="Show percentages within each expected class.")
    parser.add_argument("--output", type=Path, help="Output image path, e.g. matrix.png, matrix.pdf or matrix.svg.")
    args = parser.parse_args(argv)
    filename = "confusion_matrix_normalized.png" if args.normalize else "confusion_matrix.png"
    output_path = args.output or args.metrics_path.with_name(filename)

    # Guard against overwriting the metrics.json file with the heatmap image.
    if output_path.resolve() == args.metrics_path.resolve():
        parser.error("The output image must have a different path from the input metrics.")
    try:
        report = json.loads(args.metrics_path.read_text(encoding="utf-8"))
        figure = plot_confusion_matrix(report, normalize=args.normalize)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output_path, dpi=200, bbox_inches="tight")
        figure.clear()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Heatmap saved to {output_path}")


if __name__ == "__main__":
    main()

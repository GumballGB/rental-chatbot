# Render the final-result extraction scores and mismatches.

import json


def _percentage(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def render_metrics(report: dict) -> str:
    lines = [
        f"Whole result correct: {report['correct']}/{report['total']} ({_percentage(report['accuracy'])})",
        f"Failed extractions: {report['failed']}/{report['total']}",
        "",
        f"{'Field':<14} {'Correct/total':<15} {'Accuracy':<10} {'Supplied correct':<18} {'Invented':<10} {'Omitted':<9} Wrong",
    ]
    for field, stats in report["per_field"].items():
        supplied = f"{stats['correct_values']}/{stats['expected_values']}"
        if not stats["expected_values"]:
            supplied += " (n/a)"
        lines.append(
            f"{field:<14} {str(stats['correct']) + '/' + str(report['total']):<15} "
            f"{_percentage(stats['accuracy']):<10} {supplied:<18} "
            f"{stats['invented']:<10} {stats['omitted']:<9} {stats['wrong']}"
        )
    declined = report["declined_fields"]
    lines.extend([
        "",
        f"Declined fields exact match: {declined['correct']}/{report['total']} ({_percentage(declined['accuracy'])})",
        "Supplied correct excludes expected nulls. Failed extractions remain in accuracy denominators.",
        "Summary wording, generated IDs and received dates are not scored.",
        "",
    ])
    for case in report["cases"]:
        prefix = case["conversation_id"] + ": "
        if case["error"]:
            lines.append(prefix + case["error"])
        elif case["correct"]:
            lines.append(prefix + "correct")
        else:
            changes = [
                f"{field}: expected {json.dumps(values['expected'], ensure_ascii=False)}, "
                f"got {json.dumps(values['actual'], ensure_ascii=False)}"
                for field, values in case["mismatches"].items()
            ]
            lines.append(prefix + "; ".join(changes))
    return "\n".join(lines)

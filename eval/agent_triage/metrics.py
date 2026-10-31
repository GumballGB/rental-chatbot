# Score triage classifications without calling a model or reading files.

from typing import get_args

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from models.recommendation import Label

# Import the labels from the Recommendation model to ensure consistency with the model's definition. 
LABELS = get_args(Label)

# It is possible to not get any recommendations.
NO_RECOMMENDATION = "no recommendation"


def _index_records(records: list[dict], kind: str) -> dict:
    """
    Match records by enquiry ID and reject ambiguous input.
    
    A reminder that a record is a dictionary with at least an "enquiry_id" key. 
    The kind argument is used for error messages to indicate whether the records are 
    expected answers or predictions.
    """

    indexed = {}

    # Validate that each record has a non-empty string enquiry_id and that there are no duplicates.
    for record in records:

        # Validate that the record is a dictionary.
        enquiry_id = record.get("enquiry_id")

        if not isinstance(enquiry_id, str) or not enquiry_id.strip():
            raise ValueError(f"A non-empty {kind} enquiry_id is required.")
        if enquiry_id in indexed:
            raise ValueError(f"Duplicate {kind} enquiry_id: {enquiry_id}")
        indexed[enquiry_id] = record

    return indexed


def _ratio(numerator: int, denominator: int) -> float | None:
    """Return a ratio or None if the denominator is zero."""

    return numerator / denominator if denominator else None


def calculate_metrics(expected_answers: list[dict], predictions: list[dict]) -> dict:
    """
    Return a JSON-serializable report, joining records by enquiry_id.
    The function is meant to be used when expected answers and predictions are already 
    loaded into memory as lists of dictionaries.

    In machine learning terms, 
    the expected answers are the ground truth labels,
    the predictions are the model's outputs. 
    The function calculates various metrics to evaluate the performance of 
    the predictions against the expected answers.

    Expected rows contain expected_label and duplicates (if any). 
    The expected duplicate target is called expected_duplicated_enquiry_id. 
    
    Prediction rows contain predicted_label
    and optionally predicted_duplicated_enquiry_id and error.

    Missing predictions, null labels, and non-empty errors count as failed runs.
    They remain in the accuracy and recall denominators. Invalid labels and
    duplicate or unknown IDs raise ValueError rather than silently miscounting.
    Neither input is modified.

    Label accuracy ignores the duplicate target. Duplicate exact accuracy
    requires both the label and target, over all expected duplicate cases.
    Undefined rates are None (rendered as n/a).
    """


    expected_by_id = _index_records(expected_answers, "expected")
    predicted_by_id = _index_records(predictions, "prediction")

    # -*-*- VALIDATE AND GET METRICS -*-*- #

    # Validate that the expected labels and predicted labels are valid, 
    # and that duplicate targets are consistent with the labels.
    for enquiry_id, expected in expected_by_id.items():

        # get all the expected labels from the expected answers and check if they are valid
        label = expected.get("expected_label")

        # validation checks for the expected labels and duplicate targets
        if label not in LABELS:
            raise ValueError(f"Invalid expected label for {enquiry_id}: {label!r}")

        # get the expected duplicate target from the expected answers and check if it is valid
        target = expected.get("expected_duplicated_enquiry_id")

        # handle the validation of the expected duplicate target based on the label
        if label == "duplicate":
            if not isinstance(target, str) or not target.strip():
                raise ValueError(f"Expected duplicate target is required for {enquiry_id}.")
            if target == enquiry_id:
                raise ValueError(f"Expected duplicate {enquiry_id} cannot refer to itself.")
        elif target is not None:
            raise ValueError(f"Expected duplicate target must be null for {enquiry_id}.")

    # Validate that the predicted labels are valid and that duplicate targets are consistent with the labels.
    for enquiry_id, prediction in predicted_by_id.items():
        if enquiry_id not in expected_by_id:
            raise ValueError(f"Unknown prediction enquiry_id: {enquiry_id}")
        label = prediction.get("predicted_label")
        # An error means the run failed, even if it produced a partial label.
        if not prediction.get("error") and label is not None and label not in LABELS:
            raise ValueError(f"Invalid predicted label for {enquiry_id}: {label!r}")

    # -*-*- CALCULATE PHASE -*-*- #

    y_true = []
    y_pred = []
    failures = []

    duplicate_correct = 0

    # Loop through the expected answers and compare them with the predictions to calculate metrics.
    for enquiry_id, expected in expected_by_id.items():

        prediction = predicted_by_id.get(enquiry_id)

        if prediction is None:
            error = "No prediction recorded."
        else:
            error = prediction.get("error")
            if not error and prediction.get("predicted_label") is None:
                error = "No recommendation returned."

        # If there is an error, we record it and set the predicted label to NO_RECOMMENDATION.
        if error:
            predicted_label = NO_RECOMMENDATION
            failures.append({"enquiry_id": enquiry_id, "error": error})
        else: 
            # If there is no error, we get the predicted label from the prediction.
            predicted_label = prediction["predicted_label"]

        # We get the expected label from the expected answers
        expected_label = expected["expected_label"]
        y_true.append(expected_label)
        y_pred.append(predicted_label)

        if (
            expected_label == predicted_label == "duplicate"
            and prediction.get("predicted_duplicated_enquiry_id")
            == expected["expected_duplicated_enquiry_id"]
        ):
            duplicate_correct += 1

    columns = (*LABELS, NO_RECOMMENDATION)

    # Include failures in sklearn's labels or they would disappear from the
    # matrix. Its fifth row is always empty: no expected label is a failure.
    if y_true:
        sklearn_matrix = confusion_matrix(y_true, y_pred, labels=columns).tolist()
        class_report = classification_report(
            y_true, y_pred, labels=LABELS, output_dict=True, zero_division=0
        )
    else:
        # sklearn requires at least one sample; an empty evaluation has no rates.
        sklearn_matrix = [[0 for _ in columns] for _ in columns]
        class_report = {
            label: {"support": 0, "precision": 0.0, "recall": 0.0}
            for label in LABELS
        }
    matrix = {
        expected: {
            predicted: sklearn_matrix[row][column]
            for column, predicted in enumerate(columns)
        }
        for row, expected in enumerate(LABELS)
    }

    per_class = {}

    # Calculate per-class metrics, including support, predicted counts, true positives, 
    # false positives, false negatives, precision, and recall for each label.
    for label in LABELS:

        stats = class_report[label]
        support = int(stats["support"])
        predicted = sum(matrix[expected][label] for expected in LABELS)
        true_positive = matrix[label][label]
        per_class[label] = {
            "support": support,
            "predicted": predicted,
            "true_positive": true_positive,
            "false_positive": predicted - true_positive,
            "false_negative": support - true_positive,
            # Keep undefined rates distinct from a measured zero.
            "precision": stats["precision"] if predicted else None,
            "recall": stats["recall"] if support else None,
        }

    total = len(expected_by_id)
    correct = sum(matrix[label][label] for label in LABELS)
    duplicate_total = per_class["duplicate"]["support"]

    return {
        "total": total,
        "correct": correct,
        "accuracy": float(accuracy_score(y_true, y_pred)) if total else None,
        "failed": len(failures),
        "confusion_matrix": matrix,
        "per_class": per_class,
        "duplicate_outcomes": {
            "correct": duplicate_correct,
            "total": duplicate_total,
            "accuracy": _ratio(duplicate_correct, duplicate_total),
        },
        "failures": failures,
    }

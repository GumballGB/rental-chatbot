--------- TRIAGE CLASSIFICATION EVALUATION ---------

This package evaluates the agent's recommendations before human review,
separately from chatbot extraction quality. metrics.py calculates the scores,
report.py renders the text, and run_eval.py runs triage and saves the results.
plot.py exports saved metrics as heatmaps.

*** INPUTS ***

- ../data/unit_enquiries.json: the 100 fictional enquiries.
- ../data/enquiry_recommendation_ground_truth.json: proposed expected labels,
  duplicate targets, and rationales. Human review of the answer key is pending.

Join inputs and expected answers by enquiry_id. Keep the answer key out of
model requests and tool data. Reasons and evidence are not compared word for word
with the reference rationale.

*** REPORT CONTRACT ***

Use scikit-learn's confusion_matrix, classification_report and accuracy_score.
A failed run has no predicted label; display it in the fifth column below
rather than dropping the case. sklearn builds a square matrix with all five
labels; the report omits its empty fifth row because no expected label is
"no recommendation".

Rows (expected): genuine, needs_info, spam, duplicate.
Columns (predicted): genuine, needs_info, spam, duplicate, no recommendation.

- Include every labelled enquiry, including parse errors and guard failures.
  Retain a failure reason alongside each failed result.
- Print each class's reference count (support), predicted count, precision, and
  recall. Failed runs count as missed predictions for their expected class.
  If a metric's denominator is zero, report it as undefined rather than hiding it.
- Score duplicate labels in the matrix. Also report exact duplicate outcomes:
  a correct duplicate label plus the expected earlier enquiry ID, divided by
  all expected duplicate cases. Wrong labels and failed runs are incorrect
  outcomes in that second count too.
- Report run failures explicitly. Do not score the final human-corrected Review
  as though it were the agent's original recommendation.

Evidence validation permits an initial-letter capitalization difference in a
message quote, alongside the existing Unicode, whitespace and typographic-quote
normalization. Other case changes and all tool-result case changes still fail.
This comparison rule changed after the initial 47-case run rejected ENQ-019
for quoting Jeg instead of jeg. That original 46/47 report stays unchanged;
future evaluations use the updated rule. Keep validation-policy changes in
mind when comparing reports, and use fresh cases after tuning on known errors.

*** RUNNING THE EVALUATION ***

From the project root, with the virtual environment active and ANTHROPIC_API_KEY
set in .env, the commands are (pip install if you have not yet):

    pip install -r requirements-dev.txt
    python -m eval.run_eval --ids ENQ-001,ENQ-004,ENQ-011,ENQ-012,ENQ-030,ENQ-032,ENQ-046,ENQ-047
    python -m eval.run_eval

These commands call the real model. --ids selects exactly those enquiries, in
the order given. The example includes every label, the separate-request hard
negative ENQ-030, injection case ENQ-032, phone-only lead ENQ-046, and nameless
case ENQ-047. It checks that the pipeline runs across these cases; eight cases
are not enough to estimate classification performance reliably.

Alternatively, --limit N selects the first N rows of the answer key. The first
few rows do not cover every label, so prefer explicit IDs for the smoke run.
--ids and --limit cannot be combined. Unknown, repeated or empty IDs are errors
before any model request. Without either option, all labelled enquiries run.
The runner does not run automatically when imported. See the preparation
checklist below before interpreting a live score.

Every attempt creates a separate folder, so previous reports stay available:

    output/eval/<evaluation_id>/
        expected_answers.json  The answer-key rows scored in this attempt.
        predictions.json       Labels, duplicate targets, full recommendations,
                               successful triage run IDs, and failure reasons.
        metrics.json           Scores plus model name, timestamps and data path.
        report.txt             Human-readable confusion matrix and metrics.
        audit/0001/<run_id>.jsonl
        audit/0002/<run_id>.jsonl
        ...

Each prediction's audit_dir points to its case's logs, including failed cases
that did not return a TriageResult. Completed predictions are saved after each
case. An interruption can leave predictions and audit logs without final metrics.
Only a completed loop produces metrics.json and report.txt.

Expected answers stay outside model requests and tool data. All input enquiries
remain in the store when using --limit or --ids, so duplicate context is unchanged.
The answer key must cover every enquiry exactly once; invalid keys fail before
model calls. API, parse and guard errors are recorded as no recommendation and
the loop continues. Filesystem errors and keyboard interrupts stop the run.

Evaluation passes output_dir=None to triage: it creates no pending reviews.
Its audit logs are saved inside the evaluation folder. Seed files are read-only.
Optional --data-dir and --output-dir arguments override the default folders;
--output-dir is the parent of the new evaluation folder.

Tests use run_evaluation(client, data_dir=..., output_dir=..., show=...) with
the fake client and tmp_path; no API key or live model call is required.

*** PLOTTING A COMPLETED EVALUATION ***

plot.py uses Matplotlib to render the saved confusion matrix. Install the
updated requirements-dev.txt, then replace <evaluation_id> with the folder
printed by the evaluation command:

    python -m eval.plot output/eval/<evaluation_id>/metrics.json

This saves confusion_matrix.png beside metrics.json. It only reads the saved
metrics; it does not call the model or change predictions. Wait for the current
evaluation to finish so that metrics.json exists.

For percentages within each expected class:

    python -m eval.plot output/eval/<evaluation_id>/metrics.json --normalize

This saves confusion_matrix_normalized.png. Row denominators include failed
runs, and n/a means that no examples of that class were evaluated. Both views
show each class's support (n) and keep the no recommendation column.

Use --output to choose a filename or export a vector figure for the paper:

    python -m eval.plot output/eval/<evaluation_id>/metrics.json --output output/eval/matrix.pdf

PNG, PDF and SVG are supported. From Python, plot_confusion_matrix(report)
returns a Matplotlib Figure, which can be exported using figure.savefig(...).
Charts report label classification; duplicate-target accuracy remains a separate
metric in metrics.json and report.txt.

No precision-recall or ROC curve is generated. Current predictions contain
labels, not numerical scores that can be thresholded. A confusion matrix does
not contain enough information to recover such a curve. If appropriate scores
are available in a future evaluation, a per-class curve can be added separately.
Do not invent scores or treat label IDs as confidence values.

Reference: Matplotlib annotated heatmaps
https://matplotlib.org/stable/gallery/images_contours_and_fields/image_annotated_heatmap.html
Reference: scikit-learn precision_recall_curve (requires prediction scores)
https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html

*** DATASET LIMITATIONS AND PREPARATION ***

The 100 proposed labels are 28 genuine, 24 needs_info, 24 spam, and 24 duplicate.
Always predicting genuine would score 28/100 (28.0%) accuracy. Class counts and
per-class metrics remain necessary: one error among 24 examples changes recall
by about 4.2 percentage points. This is synthetic evaluation data, not training
data or a representative sample of real enquiries.

The original ENQ-001..ENQ-047 retain their exact inputs and answers: 22 genuine,
9 needs_info, 8 spam, 8 duplicate. ENQ-048..ENQ-100 add 53 challenge cases:
6 genuine, 15 needs_info, 16 spam and 16 duplicate. The additions cover shared
contacts for different requests, weak duplicate candidates, quoted or negated
spam vocabulary, forged roles and flags, incomplete structured fields, and
cross-language or reformatted follow-ups. Details are in data/seed_data_README.txt.
The new labels are proposed answers for human review, not conclusions from a
live model run.

All additions are dated 2026-10-30, after the original received dates. They
leave the original earlier-enquiry context intact, and same-day new cases are
excluded from each other's duplicate context. New duplicate targets are earlier
original enquiries; the difficult multi-candidate case must select the right
request rather than just a matching contact.

The normal command now evaluates all 100. --limit 47 selects the original cohort.
From Python, run_evaluation(client, ids=[f"ENQ-{n:03d}" for n in range(48, 101)])
selects only the added cohort with the same full read-only store. Keep original,
new-cohort and combined results distinct when reporting; the known cases were
used during prompt and guard development. Cohort metrics can also be calculated
from saved predictions and answer rows without repeating model calls.
The previous 46/47 result and frozen artifacts have not been rescored or changed.

Triage now receives application-computed has_name and has_contact booleans.
A field is present only if it is nonblank; contact means email OR phone.
Names and contacts stay out of the model-facing fields. Completeness is taken
from the structured fields rather than inferred from the free-text message.
The system prompt defines the labels: after ruling out spam and a supported
duplicate, a rental request is genuine with a name and one contact method, and
needs_info otherwise. Listing, move-in date, budget and currency are optional.
Shared contacts alone do not prove a duplicate, and injected instructions must
be ignored rather than automatically making a rental request spam.

Before interpreting live scores, review the proposed answer key, settle its
remaining judgement calls, and freeze the dataset. Fake-client tests verify
the flags and instructions sent to the model, not whether a live model follows
the policy. Measuring that behaviour is the evaluation's job.

Duplicate context uses strictly earlier received dates. The same-day name-swap
and injection pairs therefore do not become each other's earlier candidates.

\\\ BUILD ORDER ///

1. Done: metrics.py and tests using hand-written expected/predicted results.
   These tests require no model calls or API credentials.
2. Done: run_eval.py calls triage_enquiry once per case and records either its
   original recommendation or the run failure, then produces the report.
3. Done: runtime reports live under ../output/eval/, which is already git-ignored.

Creating this package does not run the agent, change the dataset, or approve the
reference answers.

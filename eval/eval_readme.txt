--------- TRIAGE CLASSIFICATION EVALUATION ---------

This package evaluates the agent's recommendations before human review,
separately from chatbot extraction quality. metrics.py calculates the scores,
report.py renders the text, and run_eval.py runs triage and saves the results.

*** INPUTS ***

- ../data/unit_enquiries.json: the 47 fictional enquiries.
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

*** DATASET LIMITATIONS AND PREPARATION ***

The current proposed labels are 22 genuine, 9 needs_info, 8 spam, and 8 duplicate.
Always predicting genuine would score 22/47 (46.8%) accuracy. This is still an
imbalanced evaluation set, not model training data; class counts and per-class
metrics are necessary to interpret results. The needs_info examples now cover
missing names even when both contacts are supplied, named renters with no
contact method, and neither name nor contact details. ENQ-046 is a genuine
phone-only lead; ENQ-047 needs a name despite supplying email and phone.
With eight examples in a class, one error changes recall by 12.5 percentage
points, so results remain a small synthetic evaluation.

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

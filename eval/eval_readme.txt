--------- TRIAGE CLASSIFICATION EVALUATION ---------

This package is the starting point for classification evaluation. The runner and
metrics functions have not been implemented yet. It evaluates the agent's
recommendations before human review, separately from chatbot extraction quality.

*** INPUTS ***

- ../data/unit_enquiries.json: the 47 fictional enquiries.
- ../data/enquiry_recommendation_ground_truth.json: proposed expected labels,
  duplicate targets, and rationales. Human review of the answer key is pending.

Join inputs and expected answers by enquiry_id. Keep the answer key out of
model requests and tool data. Reasons and evidence are not compared word for word
with the reference rationale.

*** REPORT CONTRACT ***

Use the standard library: a Counter of (expected_label, predicted_label)
pairs is enough. A failed run has no predicted label; display it in the fifth
column below rather than dropping the case.

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

Before live evaluation:

1. Review the proposed answer key and settle its remaining judgement calls.
2. Give triage the agreed label policy and safe contact-presence indicators.
   The current filtered view hides whether a name or contact method exists.
   Values such as has_name and has_contact can expose completeness without
   exposing the underlying personal details.
3. Review and freeze the expanded dataset before measuring model performance.

Duplicate context uses strictly earlier received dates. The same-day name-swap
and injection pairs therefore do not become each other's earlier candidates.

\\\ BUILD ORDER ///

1. Add metrics.py and tests using hand-written expected/predicted results.
   These tests require no model calls or API credentials.
2. Add a runner that calls triage_enquiry once per case and records either its
   original recommendation or the run failure, then produces the report.
3. Save runtime reports under ../output/eval/, which is already git-ignored.

Creating this package does not run the agent, change the dataset, or approve the
reference answers.

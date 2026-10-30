# Key decisions

- **A person makes the final decision.** The agent recommends a label; a reviewer
  approves or overrides it. Decided reviews cannot be overwritten. This is a
  single-reviewer terminal tool, so concurrent reviewers are outside its scope.

- **Use JSON files for this small prototype.** Keep seed inputs in `data/` and
  runtime state in `output/`. Enquiries use `enquiry_id`; recommendations use
  `run_id`; reviews link both. Python creates the run ID and returns it alongside
  the recommendation in `TriageResult`. Save each file atomically and the pending
  review last. The three files are not one transaction.

- **Give the model read-only tools.** Application code handles saves outside the
  tool loop. This makes a global `ALLOW_WRITE` flag unnecessary.

- **Filter personal data before triage.** Matching uses the original contacts
  locally; the model receives redacted text and presence flags. Tool results and
  logged matching arguments are filtered too. The chatbot collects original
  details, and the human reviewer sees them. Regex keeps redaction simple, with
  known misses for partial names and false positives for some numeric lists.

- **Keep the completeness rule simple.** After ruling out spam and a supported
  duplicate, a rental request needs a name AND (email OR phone). Budget, currency,
  listing and move-in date are optional. Use structured-field presence flags;
  extracting details from conversation belongs to the chatbot. Shared contacts
  or a matching listing/date alone do not establish a duplicate.

- **Validate recommendations and their evidence.** Send the Pydantic response
  schema to the model and validate the reply locally. Check quotes against the
  redacted message or recorded tool result. Allow an initial-letter case change
  in message quotes; keep the rest case-sensitive. Finding a quote does not
  establish that the reasoning is correct.

- **Keep evaluation answers separate from model input.** Use 100 fictional
  enquiries, retaining the original 47. Count failed runs in the results and score
  duplicate targets separately. Preserve earlier reports when the code changes.
  Full author review of the answer key is still pending.

- **Make the output limit configurable.** Two live replies hit the 1,024-token
  ceiling, so triage now defaults to 2,048 and records the setting in evaluation
  metadata. Truncated replies remain failures, with no automatic retry.

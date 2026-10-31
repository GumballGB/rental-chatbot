CHATBOT FINAL-RESULT EXTRACTION EVALUATION

Each case has a fixed conversation and one expected final result. There are no
per-turn assertions or live assistant follow-up calls. The existing production
extract_enquiry_unit_enquiry function runs once after each transcript ends.

INPUTS

    data/conversations.json   25 user/assistant transcripts ending in user done.
    data/ground_truth.json    Separate expected final values, not model input.

Answer-key review: pending; review date to be confirmed. All names, emails and
phone numbers are fictional. Assistant turns are authored fixtures,
not recorded live chatbot responses. Inventory identifiers refer to the existing
fictional listings; the office phone in CHAT-010 is an explicitly fictional decoy.

Case      User turns*  Main check                           Declined fields
CHAT-001  1            Complete English details             none
CHAT-002  1            Complete Danish details              none
CHAT-003  3            Details supplied gradually           none
CHAT-004  5            Budget/date/email corrections        none
CHAT-005  5            French follow-ups                    phone
CHAT-006  4            Danish phone-only contact            email
CHAT-007  2            Unanswered name/phone questions      none
CHAT-008  5            Unselected listing and unknown date  budget, phone
CHAT-009  5            Email correction; unknown budget     phone
CHAT-010  5            User budget/phone vs assistant data  none
CHAT-011  2            Applicant vs relative contacts       none
CHAT-012  2            Previously supplied phone removed    phone
CHAT-013  2            Previously supplied email removed    email
CHAT-014  3            Final budget/date among alternatives none
CHAT-015  2            French/English; phone undecided      none
CHAT-016  2            Danish/English; phone punctuation    none
CHAT-017  2            Long message with irrelevant numbers none
CHAT-018  2            Date ambiguity remains unresolved    none
CHAT-019  1            General question; no applicant facts none
CHAT-020  2            Numeric date explicitly clarified    none
CHAT-021  1            English pair: full sentences         none
CHAT-022  3            English pair: short text and typos    none
CHAT-023  2            Language pair: Danish                phone
CHAT-024  3            Language pair: English               phone
CHAT-025  2            Selects earlier options by reference none

* User turns exclude the final done command. This is the range of the current
fixtures, not a new five-turn limit in the interactive chatbot.

All 25 conversations form one evaluation set with one overall score. CHAT-001
through CHAT-010 are unchanged; CHAT-011 through CHAT-025 extend the same set.
New expected answers have explanatory notes and are pending author review before
live scoring; no new live score is claimed. The earlier 10/10 result applies
only to the first ten conversations, before expansion.

The runner removes done locally and appends the same extraction request used by
run_rental_chat. Neither case titles nor expected answers reach the model.
The pair_id and answer notes are also excluded from model input.
Only the final six fields and final declined_fields set are compared:

    name, email, phone, move_in_date, budget, listing_id

The source conversation is preserved. No generated enquiry IDs, received dates,
derived budget currency, or free-text summary wording are scored. The returned
summary is saved for inspection but its factual accuracy is not measured here.

SCORING RULES

- Dates use YYYY-MM-DD; the extraction prompt states that format explicitly.
- Names and IDs preserve case and accents; Unicode composition and outer spaces
  are normalized. Emails ignore case and outer spaces, matching application policy.
- Phones use the application's duplicate-matching normalization: punctuation is
  ignored, as is an optional North American country prefix. A Danish country code
  remains part of the value. Missing values are expected to be null.
- declined_fields is compared as a set, so order does not matter. An unanswered
  question or an undecided value is not an explicit refusal.
- Whole-result accuracy requires all six fields and the refusal set to match.
- Field accuracy includes correct nulls. Supplied-value accuracy/counts separately
  show whether values that were actually provided were recovered.
- Invented means a nonnull value where the key expects null; omitted means a
  missing supplied value; wrong means a different supplied value.
- Missing or failed extractions remain in accuracy denominators. No retries are
  performed. The production extractor currently has a 1,024-output-token ceiling.
- An explicit final request to remove a previously supplied contact, accompanied
  by refusal to supply that field, leaves null plus that declined_fields entry.
  This follows the existing latest-correction rule; it does not delete audit data.
- Ambiguous dates remain null until the user clarifies them. Uncertainty is not
  an explicit refusal. Alternatives mentioned by the assistant become selected
  values only when the user actually chooses them.

PAIRED CONSISTENCY

PAIR-EN (CHAT-021/022) expresses the same facts in full English sentences versus
short, typo-containing messages. PAIR-DK (CHAT-023/024) expresses the same facts
in Danish versus English. Each pair has the same expected final fields.

The report compares final extracted fields and refusals using the same phone,
email, Unicode and whitespace normalization as accuracy. It ignores summary
wording. It shows both consistent pairs and pairs with both outputs correct:
matching outputs can still both be wrong. A failed/missing extraction makes the
pair inconsistent. If --limit selects only half a pair, that pair is explicitly
not evaluated. Paired examples are related cases, not independent scenarios.

RUN

From the repository root with dependencies installed and ANTHROPIC_API_KEY set:

    python -m eval.chatbot.run_eval
    python -m eval.chatbot.run_eval --limit 2

The full command makes 25 real extraction calls. --limit 2 uses the first two
short cases. Review the new answer key before running the expanded benchmark.
The assistant responses in the transcripts are not regenerated.
Optional --data-dir and --output-dir select fixture and results parent folders.

Each attempt creates output/eval/chatbot/EVALUATION_ID/ with:

    conversations.json      The selected input transcripts.
    expected_answers.json   The selected answer-key rows.
    predictions.json        Final extractions or failure reasons, saved per case.
    usage.json              Per-response token counts, saved before parsing.
    metrics.json            Field counts, overall score, pair scores, mismatches
                            and cost estimate.
    report.txt              Readable scores, differences and cost estimate.
    cost.json               Token totals, USD estimate and pricing snapshot.
    cost_report.txt         Readable cost estimate and its limitations.

No runtime Enquiry or pending Review is created. Seed inputs stay unchanged.
Tests use the fake client and tmp_path, so no API credentials are needed.
The cost covers final extraction only, including invalid/truncated outputs.
It does not measure the cost of a live conversation. See ../eval_readme.txt
for the saved-run cost command, pricing and missing-usage limitations.

This benchmark measures extraction from fixed text. It does not establish that
the live chatbot asks good questions, uses lookup tools correctly, or produces
faithful summaries. Keep these scores separate from triage classification scores.

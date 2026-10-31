CHATBOT FINAL-RESULT EXTRACTION EVALUATION

Each case has a fixed conversation and one expected final result. There are no
per-turn assertions or live assistant follow-up calls. The existing production
extract_enquiry_unit_enquiry function runs once after each transcript ends.

INPUTS

    data/conversations.json   Ten user/assistant transcripts ending in user done.
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

* User turns exclude the final done command. This is the range of the current
fixtures, not a new five-turn limit in the interactive chatbot.

The runner removes done locally and appends the same extraction request used by
run_rental_chat. Neither case titles nor expected answers reach the model.
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

RUN

From the repository root with dependencies installed and ANTHROPIC_API_KEY set:

    python -m eval.chatbot.run_eval
    python -m eval.chatbot.run_eval --limit 2

The first command makes ten real extraction calls; the second uses the two short
complete cases. The assistant responses in the transcripts are not regenerated.
Optional --data-dir and --output-dir select fixture and results parent folders.

Each attempt creates output/eval/chatbot/EVALUATION_ID/ with:

    conversations.json      The selected input transcripts.
    expected_answers.json   The selected answer-key rows.
    predictions.json        Final extractions or failure reasons, saved per case.
    metrics.json            Field counts, accuracy and per-conversation mismatches.
    report.txt              Readable scores and expected/actual differences.

No runtime Enquiry or pending Review is created. Seed inputs stay unchanged.
Tests use the fake client and tmp_path, so no API credentials are needed.

This benchmark measures extraction from fixed text. It does not establish that
the live chatbot asks good questions, uses lookup tools correctly, or produces
faithful summaries. Keep these scores separate from triage classification scores.

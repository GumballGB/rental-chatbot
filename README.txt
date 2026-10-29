-*-*-*- RENTAL CHATBOT -*-*-*-

The Python Version of my computer is Python 3.12.7

Like all Python projects, this project requires its own virtual environment.
To activate the environment, do the following command:

--- FIRST SETUP ---
To setup this project for first-time users, you need to run the following commands;

1. Create the venv (virtual environment), the command is:

python3.12 -m venv .venv

If on LINUX, install the python venv w/ this line (it works on my computer)
sudo apt install python3-venv python3-pip

Then

python3 -m venv .venv

2. Activate the virtual environment with:

source .venv/bin/activate

3. Install the dependencies, it is found in a requirements.txt.

pip install -r requirements.txt
pip install -r requirements-dev.txt

4. Set up the key
This project uses Anthropic, copy the '.env.example' code and paste it into a new file called '.env'
You need to fill the Anthropic key placeholder 

To deactivate the venv, just type 'deactivate'

-**-**- TESTING -**-**-

To run testing, make sure you pip install the requirements-dev.txt file

python -m pytest

-**-**- RUNTIME OUTPUT AND HUMAN REVIEW -**-**-

run_rental_chat saves the complete enquiry after extraction. triage_enquiry
saves the enquiry, the guarded recommendation, and a pending Review:

output/enquiries/<enquiry_id>.json
output/recommendations/<run_id>.json
output/reviews/<enquiry_id>/<run_id>.json

The data/ seed files stay unchanged. output/ is runtime state and is ignored by git.
Both functions accept output_dir (default: the project's output/ directory).
Pass output_dir=None to skip saving runtime output; triage audit logging still
uses audit_dir. Tests should pass tmp_path or None.

The writer uses readable, indented JSON. Each file is written to a temporary
file in the destination folder, then renamed into place. The pending review is
saved last so it only appears after both bodies are available. This is atomic
per file, not a transaction across all three files.

A human decision is saved to the same review path using core.writer.save_review.
Construct a validated Review with decision approved or overridden, the reviewer,
review_date, and final outcome; overrides also require a message. The original
recommendation stays in its own file. Pending reviews have decision="pending".
Each new triage run gets a separate recommendation and review.

Once a review is approved or overridden it cannot be replaced, including by an
identical decision or a reset to pending. save_review raises
ReviewAlreadyDecidedError for these attempts, and RecommendationNotFoundError
if the required recommendation file is missing. This terminal workflow supports
one reviewer at a time; concurrent reviewers are outside its scope
Review listings must read only *.json files.

core.manual_review.load_review_item(review_path, output_dir) loads a ReviewItem
containing the review, full enquiry, and recommendation, and validates their links.
Missing, corrupt, or inconsistent files raise ReviewLoadError.

-**-**- RUN MANUAL REVIEW -**-**-

From the project root with the virtual environment active, run:

python -m core.manual_review

Use this module command rather than python core/manual_review.py. Running the
file directly does not put the project root on Python's import path, so imports
from core and models can fail. The runpy test checks the entry-point guard,
not direct-file execution outside pytest.

Enter the reviewer name (Enter uses admin). Review each enquiry and use a to
approve, o to override, s to skip, or q to quit. Overrides require an explanation
and a duplicate enquiry ID if the final label is duplicate. Approval comments
are optional. EOF or Ctrl-C during a decision quits without saving that item.

The loop saves each decided Review through the atomic writer. Skip and quit
leave pending files unchanged. An already-decided item is reported and skipped;
other saving errors propagate. The session ends with counts for approved,
overridden, skipped, and warned. Already-decided items count as both skipped
and warned. Unvisited items after quitting are not counted as skipped.

core.manual_review.run_manual_review(output_dir, reviewer, ask, show) returns
these counts as a dictionary. Defaults are the project's output/ directory,
admin, input, and print. Tests pass tmp_path, scripted answers, and a collector
for displayed text; no keyboard or model calls are needed.

-**-**- DATA GOVERNANCE -**-**-

The chatbot collects details through a model-backed conversation. Use fictional
users only in this demonstration. The triage redaction work does not anonymise
the chatbot conversation or its extraction request.

core/pii.py provides contains_pii, redact_pii, and enquiry_for_triage. These
helpers recognise common emails, North American phones, Danish +45 phones,
and local Danish numbers grouped as 12 34 56 78 (also dots/hyphens).
Full known names ignore case. Individual name parts need at least four letters
and the supplied capitalisation; accent-free spellings are accepted too.
Danish ASCII alternatives include Sørensen/Sorensen and Kjær/Kjaer; ø/Ø map
to o/O, and æ/Æ to ae/AE (also Ae). This does not identify unknown names.
This preserves lowercase park for Nina Park, but can still redact Park at the
start of a sentence. Lowercase partial signatures ("sofie here" for Sofie
Andersen), short parts such as Kim, Lee, Jo, Li, or Bo, unknown names, and
unsupported spellings can remain. Bare eight-digit numbers remain unchanged.
Grouped numbers are redacted without a phone cue: "Units: 45 50 55 60 sqm"
becomes "Units: [PHONE] sqm". We accept this false positive rather than miss
uncued local phone numbers.

this is not a complete PII detector.
Other message text and the original Enquiry are preserved. The filtered view
omits name, email, and phone fields.

triage_enquiry now uses this filtered view for its initial model request and
checks message evidence against the same redacted text. The original enquiry
is unchanged and still saved for human review. The fake-client test verifies
that its example name, email, and phone do not appear in the initial request.

The duplicate tool takes no model-supplied arguments. The application binds the
original contacts, listing, dates, and enquiry ID directly to local matching.
The prompt instructs triage to call it first; it returns filtered candidates and
matched_on fields. get_enquiry returns the same filtered view. Private name,
email, and phone arguments are omitted from triage tool-call audit events.

Tool-loop tests use email, phone, and name-based matches without model-supplied
contact values. They inspect every fake-client request, both historical tool
results, and audit events for the fixture contacts. These tests exercise the
application's data handling; they do not prove a live model will follow the
prompt or that the heuristic catches all PII.

Human review retains the original enquiry and displays a note explaining that
evidence quotes use the redacted text seen by triage.


output/ contains full enquiry bodies, including names, email addresses, and
phone numbers. Treat it as personal data. Git ignore prevents accidental
tracking; it does not encrypt the files or restrict access to them. Keep these
runtime files out of source control and restrict access when sharing or backing
up the project.





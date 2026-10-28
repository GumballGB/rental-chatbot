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
one reviewer at a time; concurrent reviewers are outside its scope (see DECISIONS.md).
Review listings must read only *.json files.

The interactive manual_review interface is still a placeholder.

-**-**- DATA GOVERNANCE -**-**-

output/ contains full enquiry bodies, including names, email addresses, and
phone numbers. Treat it as personal data. Git ignore prevents accidental
tracking; it does not encrypt the files or restrict access to them. Keep these
runtime files out of source control and restrict access when sharing or backing
up the project.





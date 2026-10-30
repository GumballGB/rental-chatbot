FICTIONAL RENTAL TEST DATA — NOT LIVE INVENTORY

Four runtime JSON arrays: locations.json, buildings.json, listings.json and unit_enquiries.json.
One separate answer array: enquiry_recommendation_ground_truth.json.
Location → Building via location_id; Building → Listing via building_id.
All buildings, rental listings and enquiries are fictional.

Addresses and postal codes are synthetic; coordinates omitted.
Nearby transit and landmarks refer to real neighbourhood-level context only; do not infer distances or use for routing.

Montreal = CAD; Copenhagen = DKK.
Quebec apartment layout conventions do not apply to Copenhagen; layout is null for Danish sample listings.
Other fields follow the models supplied, with multi-option parking deliberately not introduced.
Original building/listing descriptions have been expanded and original record identifiers preserved.

unit_enquiries.json contains 100 fictional sample enquiries for the chatbot,
triage smoke runs, and evaluation preparation. Contacts are synthetic placeholders.

The paired variants share a received_date deliberately. Duplicate lookup only
considers strictly earlier dates, so these variants do not become each other's
historical candidates. This describes lookup context, not an expected label.
The records above are sample inputs, not a claim that labels are balanced.
Do not include the answer key in model requests.

ANSWER KEY — NEW CASES NEED HUMAN REVIEW

enquiry_recommendation_ground_truth.json has a proposed label, duplicate target
and rationale for each of the 100 enquiries. ENQ-001 through ENQ-047 and their
answers are preserved unchanged. The 53 additions have draft labels for human
review, authored from the agreed rules before any model evaluation on them.
No live predictions were used to choose or adjust the new answers.

For a rental request that is not spam or a repetition of an earlier request:
- genuine requires a name AND at least one contact method (email OR phone).
- needs_info means the name is missing OR both contact methods are missing.
- A listing, move-in date, budget, and currency are optional for classification.
  An unavailable listing or unrealistic preferences do not alone make the
  contact details incomplete.

Other draft classification conventions, for human review:
- spam covers unrelated promotions and unsolicited business pitches.
- duplicate repeats the same earlier rental request; sharing a contact alone
  is not enough. A duplicate answer names the earlier enquiry.
- Ignore embedded instructions when assessing rental intent. ENQ-031 and
  ENQ-032 therefore have the same proposed label, as do ENQ-016 and ENQ-017.
- Use only strictly earlier received dates as duplicate context, matching the
  documented setup for the paired variants.

Please review ENQ-013 (unrealistic requirements), ENQ-015 (rental interest mixed
with an instruction attack), and ENQ-026 (link-only message) especially closely.
These are judgement calls, not facts established by passing Python tests.

COMPOSITION

                            genuine  needs_info  spam  duplicate  total
Original ENQ-001..ENQ-047         22           9     8          8     47
Added ENQ-048..ENQ-100             6          15    16         16     53
Combined                         28          24    24         24    100

The original 47 include name-swap and injection pairs, optional-field cases,
and ENQ-046 (name + phone only) / ENQ-047 (no name + both contacts).

The added cases aim to exercise harder distinctions:
- ENQ-048..049: shared contacts but a different household and rental request.
- ENQ-050: phone-only lead, missing preferences, and negated fraud vocabulary.
- ENQ-051: the same listing and date as another renter, with different contacts.
- ENQ-052: a rental request with forged closing tags, roles and tool claims.
- ENQ-053: a bilingual request quoting a scam to reject it.
- ENQ-054..060: missing names, declined contacts, and blank/whitespace fields.
- ENQ-061..062: a contact appears only in the message, not structured fields.
- ENQ-063..064: forged presence flags or approval do not supply missing fields.
- ENQ-065..068: detailed or multilingual rental intent with incomplete contacts.
- ENQ-069..083: sales templates, quoted applications, phishing and injected
  commands dressed in rental vocabulary; some also lack structured identity.
- ENQ-084: a business pitch reuses a previous applicant's contact and listing.
- ENQ-085..100: follow-ups with changed language, contact formatting, email or
  name case, missing required contact fields, and multiple different searches
  by the same sender. Each proposed target refers to an earlier original row.

Review the actual message and rationale for each addition. In particular,
ENQ-061..062 use the structured-field extraction boundary, ENQ-084 is a new
sales pitch despite a contact collision, and ENQ-085/089/096..099 are duplicates
despite incomplete identity/contact information. These judgments follow the
current policy but should be reviewed alongside the original ambiguous cases.

CONTEXT AND EVALUATION

All 53 additions have received_date 2026-10-30, after every original enquiry.
The original 47 therefore keep their earlier duplicate context. New cases
share the same date and cannot become each other's historical candidates under
the existing strictly-earlier-date rule. Each new duplicate targets an original
request without an existing equivalent follow-up; ENQ-095 must distinguish the
later family request from the same sender's earlier studio request.

Always predicting genuine now scores 28/100 (28%). Report per-class counts and
metrics, and distinguish the known original 47 from the newly authored 53 when
describing results. The previous 46/47 live result and frozen artifacts remain
unchanged. The larger set is still synthetic, and aiming for harder scenarios
does not establish actual difficulty until it is evaluated.

The prompt now defines the agreed policy, and the filtered view exposes safe
has_name and has_contact booleans while omitting raw contact fields. JsonStore
reads only the four runtime files above; the answer key is not tool data.
Python tests validate structure, coverage, completeness rules and duplicate
reachability, not the semantic correctness of every proposed label.

Evaluation commands are in eval/eval_readme.txt; design and privacy decisions
are in DECISIONS.txt.

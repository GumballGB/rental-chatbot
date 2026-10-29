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

unit_enquiries.json contains 47 fictional sample enquiries for the chatbot,
triage smoke runs, and evaluation preparation. Contacts are synthetic placeholders.

The paired variants share a received_date deliberately. Duplicate lookup only
considers strictly earlier dates, so these variants do not become each other's
historical candidates. This describes lookup context, not an expected label.
The records above are sample inputs, not a claim that labels are balanced.
Do not include the answer key in model requests.

GROUND-TRUTH DRAFT — HUMAN REVIEW PENDING

enquiry_recommendation_ground_truth.json has a proposed label, duplicate target
and rationale for each of the 47 enquiries. The contact-completeness rule below
was agreed with the project owner; individual proposed answers still need human
review before the file is used to score the agent. No model outputs were used
to adjust these answers.

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

Draft distribution: 22 genuine, 9 needs_info, 8 spam, and 8 duplicate.
The added ENQ-033 through ENQ-038 cover missing names, missing both contact
methods despite a supplied name, and missing both name and contacts. ENQ-039
through ENQ-041 add English, Danish and French unsolicited messages. ENQ-042
through ENQ-045 follow up on ENQ-005, ENQ-008, ENQ-009 and ENQ-010 respectively.
ENQ-046 adds a genuine lead with a name and phone but no email. ENQ-047 adds a
needs_info lead with email and phone but no name. The original 45 inputs and
proposed labels are unchanged by these two additions. The set remains
imbalanced, and metrics should include class counts. Evaluation planning is in
eval/eval_readme.txt; design and privacy decisions are in DECISIONS.txt.

Before evaluation, the agent needs the agreed classification policy and safe
presence flags such as has_name and has_contact. The current redacted view
omits raw contacts and does not yet expose their presence. JsonStore reads only
the four runtime files above, so the answer key is not loaded into tool data.

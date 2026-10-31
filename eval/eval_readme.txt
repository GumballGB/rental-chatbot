EVALUATION

agent_triage/ scores classifications on the 100 fictional enquiries.
chatbot/ scores final extraction from 25 fixed conversations as one set,
including two consistency pairs. The new answers are pending author review
before live evaluation.

Run commands from the repository root with the virtual environment active:

    python -m eval.agent_triage.run_eval --max-tokens 2048
    python -m eval.chatbot.run_eval

Both commands use the real model. Pytest uses fake clients instead. The chatbot
benchmark makes one extraction call per transcript; no intermediate turns are
generated or scored. It does not measure the quality of live follow-up questions.

Future runtime results are grouped by evaluator:

    output/eval/agent_triage/EVALUATION_ID/
    output/eval/chatbot/EVALUATION_ID/

Existing output/eval/EVALUATION_ID/ folders and archived results/ are unchanged.
Plot a triage result with its actual metrics path, including an older run:

    python -m eval.agent_triage.plot output/eval/agent_triage/EVALUATION_ID/metrics.json

The previous flat eval.run_eval and eval.plot modules have moved to agent_triage/.

COST ESTIMATES

New runs save cost.json and cost_report.txt, with the estimate also included in
metrics.json and report.txt. Both evaluators use eval/cost.py. It adds the costs
of each model response, including tool turns, parse/guard failures and truncated
outputs. The average divides by all evaluated cases, not just successful ones.

To calculate costs from an existing, completed triage run, use its actual folder:

    python -m eval.cost output/eval/agent_triage/EVALUATION_ID
    python -m eval.cost output/eval/OLDER_EVALUATION_ID

Let running evaluations finish; no restart is needed. This command never calls
the model and writes only cost.json and cost_report.txt. It leaves original
metrics, reports, predictions and audit logs intact. Keep the audit folders if
you archive results and want to recalculate costs later.

Saved pricing includes model, USD rates, source and date checked. The Haiku 5.5
snapshot checked 2026-10-31 uses $0.10 input / $0.50 output per million tokens,
or $0.50 / $2.50 when an individual prompt exceeds 100,000 input tokens:
https://platform.claude.com/docs/en/about-claude/pricing
The threshold applies per call, not to the sum of tokens across an evaluation.
Changing models requires adding a verified pricing snapshot; unknown models
are not silently priced as Haiku.

These are standard uncached-response token estimates, not billing statements.
Discounts, taxes and SDK retries/requests with no recorded response are excluded.
Caching is not enabled by these evaluators. New usage records preserve cache
counters; nonzero cache usage is flagged as unsupported rather than underpriced.
Older triage logs lack those counters and assume the original uncached setup.
Missing/corrupt logs or unknown prices make the full estimate unavailable;
the subtotal for priced recorded calls is shown separately with warnings.

Chatbot runs now checkpoint usage.json before parsing each extraction. Older
chatbot runs without usage.json cannot have their token costs recovered from
the extracted fields alone. The benchmark cost covers final extraction only;
scripted assistant turns have no API cost and live chat costs are not measured.

Details and answer-key review notes:

    agent_triage/eval_readme.txt
    chatbot/eval_readme.txt

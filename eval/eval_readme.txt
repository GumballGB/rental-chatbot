EVALUATION

agent_triage/ scores classifications on the 100 fictional enquiries.
chatbot/ scores the final extracted fields from ten fixed conversations.

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
Details and answer-key review notes:

    agent_triage/eval_readme.txt
    chatbot/eval_readme.txt

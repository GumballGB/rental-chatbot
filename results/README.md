# Evaluation results archive

Saved reports from live model evaluations on fictional data, organized into
earlier development runs and the `official_runs` series. **Answer-key review:
pending; review date to be confirmed.** The folder name records the archive
organization; it does not establish that answer-key review has been completed.

```text
results/
├── past_runs/
│   └── eval_1..eval_3/                 # Earlier triage runs
└── official_runs/
    ├── agent_triage/
    │   └── eval_4..eval_9/             # 100 enquiries per run
    └── chatbot/
        └── eval_10..eval_15/           # 25 fixed conversations per run
```

Triage folders contain `report.txt`, `cost_report.txt` (official runs) and
`confusion_matrix.png`. Chatbot folders contain `report.txt` and `cost_report.txt`.
The triage `eval_8` folder additionally contains case-level logs in `audit_eval_8/`.
These archives preserve the saved reports and scores; they do not include the
full machine-readable predictions, selected inputs, answer keys or metrics.

New evaluation attempts still write their full artifacts to Git-ignored
`output/eval/agent_triage/EVALUATION_ID/` or `output/eval/chatbot/EVALUATION_ID/`.
Archiving selected files here is separate from running an evaluation. Archive
labels such as `eval_9` are distinct from the runners' UUID evaluation IDs.

## Agent triage: official_runs

All six reports are dated 2026-10-31 and record `claude-haiku-5-5` with a
2,048-output-token ceiling per model call. Failures remain in accuracy denominators.

| Run | Correct labels | Failed runs | Exact duplicate outcomes | Artifacts |
|---|---:|---:|---:|---|
| [eval_4](official_runs/agent_triage/eval_4/report.txt) | 98/100 (98.0%) | 0/100 | 24/24 | [Heatmap](official_runs/agent_triage/eval_4/confusion_matrix.png), [cost](official_runs/agent_triage/eval_4/cost_report.txt) |
| [eval_5](official_runs/agent_triage/eval_5/report.txt) | 95/100 (95.0%) | 3/100 | 22/24 | [Heatmap](official_runs/agent_triage/eval_5/confusion_matrix.png), [cost](official_runs/agent_triage/eval_5/cost_report.txt) |
| [eval_6](official_runs/agent_triage/eval_6/report.txt) | 98/100 (98.0%) | 0/100 | 24/24 | [Heatmap](official_runs/agent_triage/eval_6/confusion_matrix.png), [cost](official_runs/agent_triage/eval_6/cost_report.txt) |
| [eval_7](official_runs/agent_triage/eval_7/report.txt) | 96/100 (96.0%) | 2/100 | 23/24 | [Heatmap](official_runs/agent_triage/eval_7/confusion_matrix.png), [cost](official_runs/agent_triage/eval_7/cost_report.txt) |
| [eval_8](official_runs/agent_triage/eval_8/report.txt) | 96/100 (96.0%) | 2/100 | 24/24 | [Heatmap](official_runs/agent_triage/eval_8/confusion_matrix.png), [cost](official_runs/agent_triage/eval_8/cost_report.txt), [audit logs](official_runs/agent_triage/eval_8/audit_eval_8/) |
| [eval_9](official_runs/agent_triage/eval_9/report.txt) | 97/100 (97.0%) | 1/100 | 24/24 | [Heatmap](official_runs/agent_triage/eval_9/confusion_matrix.png), [cost](official_runs/agent_triage/eval_9/cost_report.txt) |

Mean label accuracy: **96.7%**, range **95–98%**, with **8 failed cases across
600 predictions**. Exact duplicate outcomes total **141/144 (97.9%)**. Seven
failures were evidence-check rejections; one was a recommendation validation error.
These are repeated predictions on the same 100 enquiries.

## Chatbot final extraction: official_runs

All six reports are dated 2026-10-31 and record `claude-haiku-5-5` with a
1,024-output-token ceiling. Whole-result accuracy requires all six scored fields
and the declined-fields set to match. This evaluates extraction from fixed
transcripts, separately from triage and the interactive workflow.

| Run | Whole result correct | Failed extractions | Consistent pairs | Artifacts |
|---|---:|---:|---:|---|
| [eval_10](official_runs/chatbot/eval_10/report.txt) | 25/25 (100.0%) | 0/25 | 2/2 | [Cost](official_runs/chatbot/eval_10/cost_report.txt) |
| [eval_11](official_runs/chatbot/eval_11/report.txt) | 24/25 (96.0%) | 0/25 | 2/2 | [Cost](official_runs/chatbot/eval_11/cost_report.txt) |
| [eval_12](official_runs/chatbot/eval_12/report.txt) | 23/25 (92.0%) | 0/25 | 2/2 | [Cost](official_runs/chatbot/eval_12/cost_report.txt) |
| [eval_13](official_runs/chatbot/eval_13/report.txt) | 25/25 (100.0%) | 0/25 | 2/2 | [Cost](official_runs/chatbot/eval_13/cost_report.txt) |
| [eval_14](official_runs/chatbot/eval_14/report.txt) | 25/25 (100.0%) | 0/25 | 2/2 | [Cost](official_runs/chatbot/eval_14/cost_report.txt) |
| [eval_15](official_runs/chatbot/eval_15/report.txt) | 25/25 (100.0%) | 0/25 | 2/2 | [Cost](official_runs/chatbot/eval_15/cost_report.txt) |

Mean whole-result accuracy: **98.0%**, range **92–100%**, with **no failed
extractions across 150 predictions** on the same 25 conversations. `CHAT-025`
missed the selected listing and date in `eval_11` and `eval_12`; `CHAT-018`
incorrectly marked the move-in date as declined in `eval_12`.

## Earlier development runs: past_runs

| Archive | Enquiries | Correct | Failed | Exact duplicate targets |
|---|---:|---:|---:|---:|
| [47-case pilot](past_runs/eval_1/report.txt) | 47 | 46/47 (97.9%) | 1 | 8/8 |
| [100-case run 1](past_runs/eval_2/report.txt) | 100 | 99/100 (99.0%) | 0 | 24/24 |
| [100-case run 2](past_runs/eval_3/report.txt) | 100 | 96/100 (96.0%) | 2 | 23/24 |

### Development-run provenance

All three runs took place on 2026-10-30 with the configured model identifier
`claude-haiku-5-5` and the then-current 1,024-output-token ceiling per model call.
The old metrics metadata did not record that ceiling explicitly; the implementation
and truncation audit records establish it.

| Archive | Original evaluation ID | Heatmap |
|---|---|---|
| `eval_1` | `55efa7d4-cbb1-4b75-84c4-bef0a902351c` | [Pilot](past_runs/eval_1/confusion_matrix.png) |
| `eval_2` | `0c1f9419-0a5b-489c-bbdb-7293c1eec285` | [100-case run 1](past_runs/eval_2/confusion_matrix.png) |
| `eval_3` | `e5140f5c-e357-42a3-a1a5-de80b36eae48` | [100-case run 2](past_runs/eval_3/confusion_matrix.png) |

The pilot's rejected quote differed in its initial-letter capitalization. That
comparison rule was subsequently updated. In the second 100-case run, ENQ-027
and ENQ-058 reached the output ceiling, while ENQ-051 and ENQ-056 were accepted
false duplicate labels. ENQ-056 was also misclassified in the first 100-case run.

The current output ceiling defaults to 2,048. These earlier development reports
are not a completed repeatability study under that newer configuration. Full
author review of the 100-label answer key is pending; scores are comparisons
against its current draft labels.

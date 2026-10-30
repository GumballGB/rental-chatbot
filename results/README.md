# Archived development results

Selected reports and heatmaps from live triage evaluations on fictional data.
Full predictions, selected answer keys and audit logs remain in the corresponding
Git-ignored `output/eval/` folders. These archives preserve the original scores.

| Archive | Enquiries | Correct | Failed | Exact duplicate targets |
|---|---:|---:|---:|---:|
| [47-case pilot](eval_1/report.txt) | 47 | 46/47 (97.9%) | 1 | 8/8 |
| [100-case run 1](eval_2/report.txt) | 100 | 99/100 (99.0%) | 0 | 24/24 |
| [100-case run 2](eval_3/report.txt) | 100 | 96/100 (96.0%) | 2 | 23/24 |

## Provenance

All three runs took place on 2026-10-30 with the configured model identifier
`claude-haiku-5-5` and the then-current 1,024-output-token ceiling per model call.
The old metrics metadata did not record that ceiling explicitly; the implementation
and truncation audit records establish it.

| Archive | Original evaluation ID | Heatmap |
|---|---|---|
| `eval_1` | `55efa7d4-cbb1-4b75-84c4-bef0a902351c` | [Pilot](eval_1/confusion_matrix.png) |
| `eval_2` | `0c1f9419-0a5b-489c-bbdb-7293c1eec285` | [100-case run 1](eval_2/confusion_matrix.png) |
| `eval_3` | `e5140f5c-e357-42a3-a1a5-de80b36eae48` | [100-case run 2](eval_3/confusion_matrix.png) |

The pilot's rejected quote differed in its initial-letter capitalization. That
comparison rule was subsequently updated. In the second 100-case run, ENQ-027
and ENQ-058 reached the output ceiling, while ENQ-051 and ENQ-056 were accepted
false duplicate labels. ENQ-056 was also misclassified in the first 100-case run.

The current output ceiling defaults to 2,048. These earlier development reports
are not a completed repeatability study under that newer configuration. Full
author review of the 100-label answer key is pending; scores are comparisons
against its current draft labels.

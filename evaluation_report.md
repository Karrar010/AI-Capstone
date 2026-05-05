# Lab 7: RAGAS / automated evaluation summary

Blog Writing Agent — metrics computed over [`test_dataset.json`](test_dataset.json) using [`lab7_eval.py`](lab7_eval.py). **Faithfulness** and **answer relevancy** use RAGAS with `ChatGroq` (judge) and local HuggingFace embeddings. **Tool call accuracy** compares `researcher_node` tool names to optional `expected_tools` in the dataset (1.0 when no tools expected).

## How to refresh numbers

```powershell
$env:BWA_EVAL_SKIP_SAVE = "1"
$env:BWA_LLM_GUARD = "0"
.\venv\Scripts\python.exe lab7_eval.py --output lab7_ragas_results.json
```

Per-row scores are in `lab7_ragas_results.json`. **Answer relevancy** uses `strictness=1` for Groq compatibility (Groq rejects batched `n>1` used by higher strictness).

## Summary table (fill from `lab7_ragas_results.json` → `summary`)

| Metric | Average score | Notes |
|--------|----------------|-------|
| Faithfulness | *(run lab7_eval.py)* | Grounded in retrieved RAG chunks + evidence strings passed to RAGAS |
| Answer relevancy | *(run lab7_eval.py)* | RAGAS answer_relevancy vs user topic |
| Tool call accuracy | *(run lab7_eval.py)* | Fraction of `expected_tools` seen in `tool_trace` when researcher runs |

### Example row (development smoke, `--limit 1`, illustrative only)

| Metric | Value |
|--------|--------|
| Faithfulness | ~0.10 |
| Answer relevancy | ~0.69 |
| Tool accuracy | 1.0 |

Replace the example with your full-dataset averages after `lab7_eval.py` without `--limit`.

## Interpretation

- Low **faithfulness** often indicates the final blog added claims beyond RAG/Tavily context (hallucination risk).
- Low **answer relevancy** suggests the merged markdown drifted from the stated topic or became generic.
- **Tool accuracy** is informational: the router may skip `researcher` for vector-heavy topics, so `expected_tools: []` marks those cases as N/A (scored 1.0).

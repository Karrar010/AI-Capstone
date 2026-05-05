"""
Lab 7: Batch evaluation with RAGAS (faithfulness, answer relevancy) + tool-call accuracy.
Set BWA_EVAL_SKIP_SAVE=1 (default in main) to avoid writing .md files during runs.

Usage:
  python lab7_eval.py --limit 3 --output lab7_ragas_results.json

Requires: GROQ_API_KEY, optional TAVILY_API_KEY for research-heavy topics.
Optional LangSmith: LANGCHAIN_TRACING_V2=true LANGCHAIN_API_KEY=... LANGCHAIN_PROJECT=bwa-lab7
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

# Must run before graph / backend imports
os.environ.setdefault("BWA_EVAL_SKIP_SAVE", "1")
os.environ.setdefault("BWA_LLM_GUARD", "0")

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.checkpoint.memory import MemorySaver

from ragas import evaluate
from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, Faithfulness

from secured_graph import g


def default_inputs(topic: str) -> Dict[str, Any]:
    return {
        "topic": topic,
        "needs_research": False,
        "queries": [],
        "evidence": [],
        "rag_chunks": [],
        "plan": None,
        "sections": [],
        "merged_md": "",
        "final": "",
        "guardrail_safe": True,
        "guardrail_reason": "",
        "security_refusal": "",
        "tool_trace": [],
    }


def evidence_to_dict(e: Any) -> Dict[str, Any]:
    if hasattr(e, "model_dump"):
        return e.model_dump()
    if isinstance(e, dict):
        return e
    return {}


def build_retrieved_contexts(state: Dict[str, Any]) -> List[str]:
    chunks: List[str] = []
    for c in state.get("rag_chunks") or []:
        if isinstance(c, dict) and c.get("page_content"):
            chunks.append(str(c["page_content"])[:4000])
    for e in state.get("evidence") or []:
        d = evidence_to_dict(e)
        line = " | ".join(
            str(x)
            for x in (d.get("title"), d.get("url"), (d.get("snippet") or "")[:500])
            if x
        )
        if line.strip():
            chunks.append(line)
    return chunks if chunks else ["(no retrieval context recorded)"]


def tool_accuracy_score(expected: List[str], trace: List[Dict[str, Any]]) -> float:
    if not expected:
        return 1.0
    names = [str(t.get("tool_name", "")) for t in trace]
    hits = sum(
        1
        for exp in expected
        if any(exp == n or exp in n or n in exp for n in names if n)
    )
    return hits / len(expected)


def nanmean(values: List[float]) -> float:
    xs = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not xs:
        return float("nan")
    return sum(xs) / len(xs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parent / "test_dataset.json")
    parser.add_argument("--limit", type=int, default=0, help="Max rows (0 = all)")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "lab7_ragas_results.json")
    args = parser.parse_args()

    rows = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    eval_app = g.compile(checkpointer=MemorySaver(), interrupt_before=[])

    lc_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    ragas_llm = LangchainLLMWrapper(lc_llm)
    emb = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )

    run_records: List[Dict[str, Any]] = []
    ragas_samples: List[SingleTurnSample] = []

    for row in rows:
        tid = f"lab7-{uuid.uuid4().hex[:10]}"
        cfg = {"configurable": {"thread_id": tid}}
        topic = row["topic"]
        out = eval_app.invoke(default_inputs(topic), config=cfg)
        if not isinstance(out, dict):
            out = dict(out)

        merged = (out.get("merged_md") or "").strip()
        if not merged:
            merged = (out.get("final") or "").strip() or "(empty output)"

        contexts = build_retrieved_contexts(out)
        trace = out.get("tool_trace") or []
        exp_tools = row.get("expected_tools") or []
        t_acc = tool_accuracy_score(exp_tools, trace)

        run_records.append(
            {
                "id": row.get("id"),
                "topic": topic,
                "category": row.get("category"),
                "tool_accuracy": t_acc,
                "expected_tools": exp_tools,
                "tool_trace": trace,
                "response_len": len(merged),
            }
        )

        ragas_samples.append(
            SingleTurnSample(
                user_input=topic,
                response=merged[:12000],
                retrieved_contexts=contexts,
                reference=row.get("reference_answer"),
            )
        )

    # strictness=1: Groq rejects batched completion settings used when strictness>1 for some models
    metrics = [Faithfulness(), AnswerRelevancy(strictness=1)]
    eval_ds = EvaluationDataset(samples=ragas_samples)
    ragas_result = evaluate(
        eval_ds,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=emb,
        raise_exceptions=False,
        show_progress=True,
    )

    faith_vals = list(ragas_result["faithfulness"])
    rel_vals = list(ragas_result["answer_relevancy"])
    tool_vals = [r["tool_accuracy"] for r in run_records]

    summary = {
        "average_faithfulness": nanmean([float(x) for x in faith_vals if x == x]),
        "average_answer_relevancy": nanmean([float(x) for x in rel_vals if x == x]),
        "average_tool_accuracy": nanmean(tool_vals),
        "num_runs": len(run_records),
    }

    out_payload = {
        "summary": summary,
        "per_run": [
            {
                **run_records[i],
                "faithfulness": faith_vals[i] if i < len(faith_vals) else None,
                "answer_relevancy": rel_vals[i] if i < len(rel_vals) else None,
            }
            for i in range(len(run_records))
        ],
    }

    args.output.write_text(json.dumps(out_payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()

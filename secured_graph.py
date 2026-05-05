"""
Lab 6: Secured LangGraph — guardrail_node before router, alert_node short-circuit, output sanitization.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langchain_groq import ChatGroq

from bwa_backend import (
    State,
    fanout,
    merge_content,
    orchestrator_node,
    rag_retrieve_node,
    researcher_node,
    router_node,
    route_next,
    save_blog,
    worker_node,
)
from guardrails_config import (
    STANDARD_REFUSAL,
    run_input_guards,
    sanitize_markdown_output,
)

# Smaller / faster model for intent classification (Approach B)
guard_judge_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)


def guardrail_node(state: State) -> dict:
    topic = state.get("topic") or ""
    safe, reason = run_input_guards(topic, judge_llm=guard_judge_llm)
    if safe:
        return {"guardrail_safe": True, "guardrail_reason": ""}
    return {"guardrail_safe": False, "guardrail_reason": reason}


def route_after_guardrail(state: State) -> Literal["router", "alert_node"]:
    if state.get("guardrail_safe", False):
        return "router"
    return "alert_node"


def alert_node(state: State) -> dict:
    return {
        "security_refusal": STANDARD_REFUSAL,
        "merged_md": "",
        "final": STANDARD_REFUSAL,
    }


def output_sanitize_node(state: State) -> dict:
    md = state.get("merged_md") or ""
    return {"merged_md": sanitize_markdown_output(md)}


g = StateGraph(State)
g.add_node("guardrail_node", guardrail_node)
g.add_node("alert_node", alert_node)
g.add_node("router", router_node)
g.add_node("researcher", researcher_node)
g.add_node("rag_retrieve", rag_retrieve_node)
g.add_node("orchestrator", orchestrator_node)
g.add_node("worker", worker_node)
g.add_node("merge_content", merge_content)
g.add_node("output_sanitize_node", output_sanitize_node)
g.add_node("save_blog", save_blog)

g.add_edge(START, "guardrail_node")
g.add_conditional_edges(
    "guardrail_node",
    route_after_guardrail,
    {"router": "router", "alert_node": "alert_node"},
)
g.add_edge("alert_node", END)
g.add_conditional_edges("router", route_next, {"researcher": "researcher", "rag_retrieve": "rag_retrieve"})
g.add_edge("researcher", "rag_retrieve")
g.add_edge("rag_retrieve", "orchestrator")
g.add_conditional_edges("orchestrator", fanout, ["worker"])
g.add_edge("worker", "merge_content")
g.add_edge("merge_content", "output_sanitize_node")
g.add_edge("output_sanitize_node", "save_blog")
g.add_edge("save_blog", END)

_root = Path(__file__).resolve().parent
_checkpoint_path = Path(os.getenv("CHECKPOINT_SQLITE_PATH", str(_root / "checkpoint_db.sqlite")))


def build_compiled_app(checkpointer: Any):
    """Compile the secured graph with a caller-owned checkpointer (e.g. FastAPI lifespan)."""
    return g.compile(checkpointer=checkpointer, interrupt_before=["save_blog"])


_sqlite_cm: SqliteSaver | None = None
_default_checkpointer: SqliteSaver | None = None
_default_app = None


def _ensure_default_app():
    """Lazy singleton for Streamlit and scripts that import ``app`` or ``checkpointer``."""
    global _sqlite_cm, _default_checkpointer, _default_app
    if _default_app is not None:
        return
    _sqlite_cm = SqliteSaver.from_conn_string(str(_checkpoint_path))
    _default_checkpointer = _sqlite_cm.__enter__()
    _default_app = build_compiled_app(_default_checkpointer)


def __getattr__(name: str):
    if name == "app":
        _ensure_default_app()
        return _default_app
    if name == "checkpointer":
        _ensure_default_app()
        return _default_checkpointer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["app", "checkpointer", "g", "build_compiled_app"]

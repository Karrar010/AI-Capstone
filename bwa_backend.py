"""
Blog Writing Agent - Lab Requirements Only
Part A: RAG (Lab 2), ReAct (Lab 3), Multi-Agent (Lab 4), HITL (Lab 5), Security (Lab 6)
"""
from __future__ import annotations

import json
import operator
import os
import re
from pathlib import Path
from typing import TypedDict, List, Optional, Annotated

from pydantic import BaseModel, Field

from langgraph.types import Send
from langgraph.prebuilt import ToolNode

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import BaseTool
from dotenv import load_dotenv

load_dotenv()

from bwa_rag import retrieve_from_knowledge_base
from bwa_tools import tavily_search_tool, retrieve_from_knowledge_base_tool
from guardrails_config import sanitize_rag_chunks

# ----------------------------- Schemas -----------------------------
class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(..., description="What reader should understand.")
    bullets: List[str] = Field(..., min_length=2, max_length=5)
    target_words: int = Field(..., ge=50, le=400)


class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    tasks: List[Task]


class EvidenceItem(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None


class RouterDecision(BaseModel):
    needs_research: bool
    queries: List[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    evidence: List[EvidenceItem] = Field(default_factory=list)


class State(TypedDict):
    topic: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    rag_chunks: List[dict]
    plan: Optional[Plan]
    sections: Annotated[List[tuple[int, str]], operator.add]
    merged_md: str
    final: str
    guardrail_safe: bool
    guardrail_reason: str
    security_refusal: str
    tool_trace: Annotated[List[dict], operator.add]


# ----------------------------- LLM -----------------------------
llm = ChatGroq(model="llama-3.3-70b-versatile")

# ----------------------------- Task 1: RAG Node (Lab 2) -----------------------------
def rag_retrieve_node(state: State) -> dict:
    """RAG: retrieve domain knowledge and augment context."""
    chunks = retrieve_from_knowledge_base(query=state["topic"], k=3)
    return {"rag_chunks": sanitize_rag_chunks(chunks)}

# ----------------------------- Router -----------------------------
def router_node(state: State) -> dict:
    decider = llm.with_structured_output(RouterDecision)
    d = decider.invoke([
        SystemMessage(content="Decide if web research needed for this blog topic. needs_research=true for news/latest/2026. Output 2-5 queries if needed."),
        HumanMessage(content=state["topic"]),
    ])
    return {"needs_research": d.needs_research, "queries": d.queries}


def route_next(state: State) -> str:
    return "researcher" if state["needs_research"] else "rag_retrieve"

# ----------------------------- Task 2: ReAct Researcher (Lab 3) -----------------------------
RESEARCHER_TOOLS: List[BaseTool] = [tavily_search_tool, retrieve_from_knowledge_base_tool]


def researcher_node(state: State) -> dict:
    """ReAct: Agent reasons, calls tools, observes. Researcher persona - tools: search, retrieve only."""
    topic = state["topic"]
    queries = (state.get("queries") or [])[:5]
    tool_trace: List[dict] = []

    messages = [
        SystemMessage(content=f"You are a Researcher. Use tavily_search_tool and retrieve_from_knowledge_base_tool. Topic: {topic}. Queries: {queries}. Call tools 2-3 times, then stop."),
        HumanMessage(content=f"Gather evidence for blog: {topic}"),
    ]

    for _ in range(4):
        resp = llm.bind_tools(RESEARCHER_TOOLS).invoke(messages)
        messages.append(resp)
        tool_calls = getattr(resp, "tool_calls", []) or []
        for tc in tool_calls:
            if isinstance(tc, dict):
                name = tc.get("name", "")
                args = tc.get("args", {})
            else:
                name = getattr(tc, "name", "") or ""
                args = getattr(tc, "args", {}) or {}
            tool_trace.append({"tool_name": name, "args": args})
        if not tool_calls:
            break
        tool_result = ToolNode(RESEARCHER_TOOLS).invoke({"messages": messages})
        messages.extend(tool_result.get("messages", []))

    raw = []
    for m in messages:
        c = getattr(m, "content", None)
        if c and isinstance(c, str) and "http" in c:
            raw.append({"content": c[:500]})
    raw_text = json.dumps(raw[-6:], default=str) if raw else "[]"

    pack = llm.with_structured_output(EvidencePack).invoke([
        SystemMessage(content="Extract EvidenceItem with url, title from raw. Only items with url."),
        HumanMessage(content=raw_text),
    ])
    dedup = {e.url: e for e in pack.evidence if e.url}
    return {"evidence": list(dedup.values()), "tool_trace": tool_trace}

# ----------------------------- Task 3: Multi-Agent - Writer (Lab 4) -----------------------------
def orchestrator_node(state: State) -> dict:
    """Writer persona: no search/retrieve tools. Uses evidence + rag_chunks from Researcher."""
    evidence = state.get("evidence", [])
    rag = state.get("rag_chunks", [])
    rag_text = "\n".join(c.get("page_content", "") for c in rag[:4] if c.get("page_content"))

    plan = llm.with_structured_output(Plan).invoke([
        SystemMessage(content="Create blog outline. 4-6 tasks, each with goal, 2-5 bullets, target_words. Use evidence and guidelines."),
        HumanMessage(content=f"Topic: {state['topic']}\nEvidence: {[e.model_dump() for e in evidence][:8]}\nGuidelines: {rag_text[:800]}"),
    ])
    return {"plan": plan}


def fanout(state: State):
    p = state["plan"]
    return [
        Send("worker", {"task": t.model_dump(), "topic": state["topic"], "plan": p.model_dump(), "evidence": [e.model_dump() for e in state.get("evidence", [])], "rag_chunks": state.get("rag_chunks", [])})
        for t in p.tasks
    ]


def worker_node(payload: dict) -> dict:
    """Writer persona: writes sections. No tools."""
    task = Task(**payload["task"])
    plan = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]
    rag = payload.get("rag_chunks", [])
    rag_text = "\n".join(c.get("page_content", "")[:150] for c in rag[:2] if c.get("page_content"))
    evidence_text = "\n".join(f"- {e.title} | {e.url}" for e in evidence[:10])

    md = llm.invoke([
        SystemMessage(content="Write one Markdown section. Start with ## Title. Cover bullets. Cite evidence URLs."),
        HumanMessage(content=f"Blog: {plan.blog_title}\nSection: {task.title}\nGoal: {task.goal}\nBullets: {task.bullets}\nEvidence:\n{evidence_text}\nGuidelines: {rag_text}"),
    ]).content.strip()
    return {"sections": [(task.id, md)]}


def merge_content(state: State) -> dict:
    p = state["plan"]
    ordered = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    return {"merged_md": f"# {p.blog_title}\n\n" + "\n\n".join(ordered)}


# ----------------------------- Task 4: HITL - High-risk tool (Lab 5) -----------------------------
def save_blog(state: State) -> dict:
    """High-risk: writes file to disk. HITL interrupts BEFORE this."""
    p = state["plan"]
    md = state["merged_md"]
    slug = re.sub(r"\s+", "_", re.sub(r"[^a-z0-9 _-]+", "", p.blog_title.strip().lower())).strip("_") or "blog"
    skip = os.getenv("BWA_EVAL_SKIP_SAVE", "").strip().lower() in ("1", "true", "yes", "on")
    if not skip:
        Path(f"{slug}.md").write_text(md, encoding="utf-8")
    return {"final": md}


def __getattr__(name: str):
    if name == "app":
        from secured_graph import app as _app
        return _app
    if name == "checkpointer":
        from secured_graph import checkpointer as _cp
        return _cp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

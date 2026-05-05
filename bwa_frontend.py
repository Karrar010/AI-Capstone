"""
Blog Writing Agent Frontend - Lab Requirements Only
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, List, Iterator, Tuple

import streamlit as st

from bwa_backend import app


def try_stream(graph_app, inputs: Dict[str, Any], config: Dict[str, Any]) -> Iterator[Tuple[str, Any]]:
    try:
        for step in graph_app.stream(inputs, config=config, stream_mode="updates"):
            yield ("updates", step)
    except Exception:
        pass
    try:
        state = graph_app.get_state(config)
        if state:
            yield ("interrupt", state.values) if state.next else ("final", state.values)
    except Exception:
        try:
            yield ("final", graph_app.invoke(inputs, config=config))
        except Exception:
            pass


def extract_state(step_payload: Any, current: Dict) -> Dict:
    if isinstance(step_payload, dict) and step_payload:
        inner = next(iter(step_payload.values()))
        current.update(inner) if isinstance(inner, dict) else current.update(step_payload)
    return current


st.set_page_config(page_title="Blog Agent", layout="wide")
st.title("Blog Writing Agent")

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4())[:8]

with st.sidebar:
    topic = st.text_area("Topic", height=80)
    thread_id = st.text_input("Session (thread_id)", value=st.session_state["thread_id"], help="For session recovery")
    st.session_state["thread_id"] = thread_id or st.session_state["thread_id"]
    run_btn = st.button("Generate Blog", type="primary")

if "last_out" not in st.session_state:
    st.session_state["last_out"] = None

tab_plan, tab_evidence, tab_preview, tab_logs = st.tabs(["Plan", "Evidence", "Preview", "Logs"])
logs: List[str] = []


if run_btn:
    if not (topic or "").strip():
        st.warning("Enter a topic.")
        st.stop()

    inputs = {
        "topic": topic.strip(),
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
    config = {"configurable": {"thread_id": st.session_state["thread_id"]}}

    status = st.status("Running…", expanded=True)
    last_node = None
    interrupted = False
    interrupt_state = None

    for kind, payload in try_stream(app, inputs, config):
        if kind == "interrupt":
            interrupted = True
            interrupt_state = payload
            break
        if kind == "updates":
            node = next(iter(payload.keys()), None) if payload else None
            if node and node != last_node:
                status.write(f"Node: {node}")
                last_node = node
            logs.append(json.dumps(payload, default=str)[:600])
        elif kind == "final":
            st.session_state["last_out"] = payload
            status.update(label="Done", state="complete", expanded=False)

    if interrupted and interrupt_state:
        status.update(label="Human approval needed", state="complete", expanded=True)
        st.session_state["hitl_state"] = interrupt_state
        st.session_state["hitl_config"] = config
        st.rerun()

# HITL: Edit proposed content before save (high-risk action)
if "hitl_state" in st.session_state and st.session_state.get("hitl_state"):
    s = st.session_state["hitl_state"]
    merged = s.get("merged_md", "")
    st.warning("**Human-in-the-Loop:** Edit the proposed blog content before saving (writes file).")
    edited = st.text_area("Edit content", value=merged, height=300)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve"):
            app.update_state(st.session_state["hitl_config"], {"merged_md": edited})
            out = app.invoke(None, config=st.session_state["hitl_config"])
            st.session_state["last_out"] = out
            del st.session_state["hitl_state"]
            del st.session_state["hitl_config"]
            st.rerun()
    with col2:
        if st.button("Cancel"):
            # Proceed with original (no edit)
            out = app.invoke(None, config=st.session_state["hitl_config"])
            st.session_state["last_out"] = out
            del st.session_state["hitl_state"]
            del st.session_state["hitl_config"]
            st.rerun()
    st.stop()

out = st.session_state.get("last_out")
if out:
    if out.get("guardrail_safe") is False:
        st.error("**Request blocked by security guardrails**")
        st.warning(out.get("security_refusal") or out.get("final") or "This request was not allowed.")
        if out.get("guardrail_reason"):
            st.caption(f"Reason (debug): {out['guardrail_reason']}")
    with tab_plan:
        if out.get("guardrail_safe") is False:
            st.info("No plan — request did not pass input guardrails.")
        plan_obj = out.get("plan")
        if plan_obj:
            pd = plan_obj.model_dump() if hasattr(plan_obj, "model_dump") else (plan_obj if isinstance(plan_obj, dict) else {})
            st.write("**Title:**", pd.get("blog_title"))
            st.write("**Audience:**", pd.get("audience"))
            for t in pd.get("tasks", []):
                st.write(f"- {t.get('title')} ({t.get('target_words')} words)")
        else:
            st.info("No plan.")

    with tab_evidence:
        ev = out.get("evidence") or []
        if ev:
            for e in ev:
                d = e.model_dump() if hasattr(e, "model_dump") else e
                st.write(f"- [{d.get('title','')}]({d.get('url','')})")
        else:
            st.info("No evidence.")

    with tab_preview:
        md = out.get("final") or ""
        if out.get("guardrail_safe") is False and (out.get("security_refusal") or md):
            st.markdown(out.get("security_refusal") or md)
        elif md:
            st.markdown(md)
            title = (plan_obj.blog_title if hasattr(plan_obj, "blog_title") else (plan_obj.get("blog_title") if isinstance(plan_obj, dict) else "blog")) if plan_obj else "blog"
            slug = re.sub(r"\s+", "_", re.sub(r"[^a-z0-9 _-]+", "", str(title).lower())).strip("_") or "blog"
            st.download_button("Download MD", data=md.encode("utf-8"), file_name=f"{slug}.md", mime="text/markdown")
        else:
            st.warning("No content.")

    with tab_logs:
        st.session_state.setdefault("logs", []).extend(logs)
        st.text_area("Log", value="\n".join(st.session_state.get("logs", [])[-50:]), height=300)
else:
    st.info("Enter a topic and click Generate Blog.")

"""
Lab 8: FastAPI service for the Blog Writing Agent (LangGraph + checkpointer).
Run: uvicorn main:app --reload --host 127.0.0.1 --port 8000

Lab 9: Set POSTGRES_URI for Postgres checkpointer (Docker Compose). Otherwise uses SQLite
at CHECKPOINT_SQLITE_PATH (default: ./checkpoint_db.sqlite).
"""
from __future__ import annotations

import json
import os
import traceback
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv()

from secured_graph import build_compiled_app
from schema import ChatRequest, ChatResponse

CHECKPOINT_PATH = Path(
    os.getenv(
        "CHECKPOINT_SQLITE_PATH",
        str(Path(__file__).resolve().parent / "checkpoint_db.sqlite"),
    )
)


def graph_inputs_from_message(message: str) -> Dict[str, Any]:
    return {
        "topic": message.strip(),
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


def build_chat_response(values: Dict[str, Any], has_next: bool) -> ChatResponse:
    if values.get("guardrail_safe") is False:
        return ChatResponse(
            final_answer=values.get("security_refusal") or values.get("final") or "",
            status="blocked",
        )
    if has_next:
        return ChatResponse(
            final_answer=values.get("merged_md") or values.get("final") or "",
            status="interrupted_awaiting_hitl",
        )
    return ChatResponse(
        final_answer=values.get("final") or values.get("merged_md") or "",
        status="completed",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    postgres_uri = os.getenv("POSTGRES_URI", "").strip()
    with ExitStack() as stack:
        if postgres_uri:
            from langgraph.checkpoint.postgres import PostgresSaver

            checkpointer = stack.enter_context(PostgresSaver.from_conn_string(postgres_uri))
            checkpointer.setup()
        else:
            checkpointer = stack.enter_context(SqliteSaver.from_conn_string(str(CHECKPOINT_PATH)))
        app.state.graph = build_compiled_app(checkpointer)
        yield


app = FastAPI(title="Blog Writing Agent API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": body.thread_id}}
    inputs = graph_inputs_from_message(body.message)

    try:
        await graph.ainvoke(inputs, config=config)
        snap = await graph.aget_state(config)
    except Exception as e:
        return ChatResponse(
            final_answer=str(e)[:2000],
            status="error",
        )

    if snap is None or snap.values is None:
        return ChatResponse(final_answer="", status="error")

    values = dict(snap.values)
    has_next = bool(snap.next)
    return build_chat_response(values, has_next)


@app.post("/stream")
async def stream_chat(body: ChatRequest, request: Request) -> StreamingResponse:
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": body.thread_id}}
    inputs = graph_inputs_from_message(body.message)

    async def sse() -> AsyncIterator[str]:
        try:
            async for chunk in graph.astream(inputs, config=config, stream_mode="updates"):
                line = json.dumps(chunk, default=str)
                yield f"data: {line}\n\n"
            snap = await graph.aget_state(config)
            if snap and snap.values:
                v = snap.values
                tail = {
                    "event": "final_snapshot",
                    "next": list(snap.next) if snap.next else [],
                    "guardrail_safe": v.get("guardrail_safe"),
                    "has_merged_md": bool(v.get("merged_md")),
                    "merged_md_len": len(v.get("merged_md") or ""),
                }
            else:
                tail = {"event": "final_snapshot", "next": []}
            yield f"data: {json.dumps(tail, default=str)}\n\n"
        except Exception as e:
            err = {"event": "error", "detail": str(e), "trace": traceback.format_exc()}
            yield f"data: {json.dumps(err, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")

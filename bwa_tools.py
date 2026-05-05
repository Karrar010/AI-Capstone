"""
Project-specific tools with @tool decorator and input validation - Lab 3: Reasoning Loop
"""
from __future__ import annotations

import os
from typing import Optional

from langchain_core.tools import tool
from pydantic import Field

from bwa_rag import retrieve_from_knowledge_base


@tool
def tavily_search_tool(
    query: str = Field(..., description="Search query for web search"),
    max_results: int = Field(5, ge=1, le=10, description="Max results to return (1-10)"),
) -> str:
    """
    Search the web for up-to-date information. Use for news, releases, pricing.
    Input: query (required), max_results (optional, 1-10).
    Returns: JSON string of search results.
    """
    if not os.getenv("TAVILY_API_KEY"):
        return "TAVILY_API_KEY not set. Cannot search."
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        tool_impl = TavilySearchResults(max_results=max_results)
        results = tool_impl.invoke({"query": query})
        out = []
        for r in results or []:
            out.append({
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": (r.get("content") or r.get("snippet") or "")[:300],
                "published_at": r.get("published_date") or r.get("published_at"),
            })
        import json
        return json.dumps(out, default=str)
    except Exception as e:
        return f"Search failed: {e}"


@tool
def retrieve_from_knowledge_base_tool(
    query: str = Field(..., description="Query to retrieve relevant domain knowledge"),
    k: int = Field(4, ge=1, le=10, description="Number of chunks to retrieve (1-10)"),
) -> str:
    """
    Retrieve relevant chunks from the domain knowledge base (blog writing guidelines).
    Use for structural advice, citation rules, tone guidelines.
    Input: query (required), k (optional, 1-10).
    Returns: Concatenated text of retrieved chunks.
    """
    chunks = retrieve_from_knowledge_base(query=query, k=k)
    if not chunks:
        return "No relevant knowledge found."
    parts = [c.get("page_content", "") for c in chunks if c.get("page_content")]
    return "\n\n---\n\n".join(parts)

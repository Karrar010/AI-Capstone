"""
Standalone MCP Client - Part B Task 2

Architecture (clearly separated):
- Model: Groq LLM - reasons and decides which tool to call
- Context: Tool schemas from MCP + user query (exchanged via MCP session)
- Tools: Exposed by MCP server (word_count, estimate_reading_time)
- Execution: MCP client - connects, discovers, invokes via protocol, handles responses

Demonstrates: Model accesses tools through MCP (not direct function calls).

Run the server first: python mcp_server.py
Then run: python mcp_client.py
"""
import asyncio
import json
import os
from pathlib import Path

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _tools_to_prompt(tools: list) -> str:
    """Format MCP tools for LLM context."""
    lines = []
    for t in tools:
        desc = t.description or ""
        lines.append(f"- {t.name}: {desc}")
    return "\n".join(lines)


async def main():
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        print("Install mcp: pip install mcp")
        return

    if not os.getenv("GROQ_API_KEY"):
        print("Set GROQ_API_KEY in .env")
        return

    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage
    from pydantic import BaseModel, Field

    class ToolChoice(BaseModel):
        tool_name: str = Field(..., description="Name of the tool to call")
        arguments: dict = Field(default_factory=dict, description="Tool arguments as JSON object")

    url = "http://127.0.0.1:8000/mcp"
    user_query = "estimate reading time: The quick brown fox jumps over the lazy dog."

    print("--- Execution Layer: Connecting to MCP Server ---")
    async with streamable_http_client(url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Context: Tool discovery via MCP
            tools_result = await session.list_tools()
            print("\n--- Context: Tool Discovery (from MCP) ---")
            for t in tools_result.tools:
                print(f"  - {t.name}: {t.description or ''}")

            tools_desc = _tools_to_prompt(tools_result.tools)
            tool_names = [t.name for t in tools_result.tools]

            # Model: LLM decides which tool to call (via MCP, not direct Python)
            print("\n--- Model: LLM selects tool via MCP schema (no direct calls) ---")
            llm = ChatGroq(model="llama-3.3-70b-versatile")
            chooser = llm.with_structured_output(ToolChoice)
            choice = chooser.invoke([
                SystemMessage(content=f"Available tools (from MCP server):\n{tools_desc}\n\nChoose ONE tool and arguments. Output tool_name and arguments JSON."),
                HumanMessage(content=user_query),
            ])

            if choice.tool_name not in tool_names:
                print(f"Model chose unknown tool: {choice.tool_name}. Using word_count.")
                choice.tool_name = "word_count"
                choice.arguments = {"text": user_query.split(": ", 1)[-1] if ": " in user_query else user_query}

            # Execution: Invoke tool via MCP protocol (not direct function call)
            print(f"\n--- Execution: Invoking {choice.tool_name} via MCP ---")
            result = await session.call_tool(choice.tool_name, arguments=choice.arguments)

            # Response handling
            out = [{"type": c.type, "text": getattr(c, "text", str(c))} for c in result.content]
            print("Response:", json.dumps(out, indent=2))

    print("\n--- Done (Model → Context → Tools → Execution) ---")


if __name__ == "__main__":
    asyncio.run(main())

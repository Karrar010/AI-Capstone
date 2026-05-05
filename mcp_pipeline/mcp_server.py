"""
Standalone MCP Server - Part B Task 1
Exposes tools via MCP protocol.

Run: python mcp_server.py
Then run mcp_client.py in another terminal.
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Blog Tools Server", host="127.0.0.1", port=8000)


@mcp.tool()
def word_count(text: str) -> dict:
    """
    Count words in the given text.
    Input: text (required).
    Output: {"word_count": int, "char_count": int}
    """
    words = len(text.split()) if text else 0
    chars = len(text) if text else 0
    return {"word_count": words, "char_count": chars}


@mcp.tool()
def estimate_reading_time(text: str, wpm: int = 200) -> dict:
    """
    Estimate reading time in minutes.
    Input: text (required), wpm (optional, words per minute, default 200).
    Output: {"minutes": float, "words": int}
    """
    words = len(text.split()) if text else 0
    minutes = round(words / max(wpm, 1), 2)
    return {"minutes": minutes, "words": words}


if __name__ == "__main__":
    # Use streamable-http to avoid Windows stdio subprocess issues
    mcp.run(transport="streamable-http")

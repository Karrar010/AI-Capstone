"""
Lab 4: Multi-Agent Configuration
Defines specialized personas, roles, and tool restrictions for the Blog Writing Agent team.
"""
from __future__ import annotations

RESEARCHER = {
    "name": "Researcher",
    "role": "Research specialist who gathers evidence and raw data for blog content.",
    "backstory": "Focused solely on finding accurate, up-to-date information. Does not write or edit.",
    "tools": ["tavily_search_tool", "retrieve_from_knowledge_base_tool"],
    "tool_restriction": "ONLY these tools. No writing or file operations.",
}

WRITER = {
    "name": "Writer",
    "role": "Content synthesis specialist who creates blog sections from evidence.",
    "backstory": "Takes evidence and guidelines from Researcher, produces polished markdown sections.",
    "tools": [],  # No tools - receives context from Researcher via state handover
    "tool_restriction": "No tools. Uses only evidence and RAG chunks passed from Researcher.",
}

PERSONAS = {
    "researcher": RESEARCHER,
    "writer": WRITER,
}


def get_researcher_tools():
    """Return tool list for Researcher agent. Used by bwa_backend."""
    from bwa_tools import tavily_search_tool, retrieve_from_knowledge_base_tool
    return [tavily_search_tool, retrieve_from_knowledge_base_tool]


def get_writer_tools():
    """Return empty list - Writer has no tools."""
    return []

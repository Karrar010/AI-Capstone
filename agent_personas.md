# Agent Personas (Lab 4)

## Researcher

- **Role:** Research specialist who gathers evidence and raw data for blog content.
- **Goal:** Collect accurate, relevant information (web search results, domain guidelines) for the given blog topic.
- **Restricted Toolset:**
  - `tavily_search_tool` – Web search for up-to-date information
  - `retrieve_from_knowledge_base_tool` – Retrieve domain guidelines from the vector store
- **Does NOT have:** Writing tools, file write, or any editing capabilities.

## Writer

- **Role:** Content synthesis specialist who creates blog sections from evidence.
- **Goal:** Produce polished markdown sections using evidence and guidelines provided by the Researcher.
- **Restricted Toolset:** None. The Writer receives all context via state handover (evidence, RAG chunks) and uses only the LLM to generate content.
- **Does NOT have:** Search, retrieval, or any external tools.

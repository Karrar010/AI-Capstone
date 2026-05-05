"""
RAG Pipeline for Blog Writing Agent - Lab 2: Knowledge Engineering & Domain Grounding
Uses ingest_data.py for loading, cleaning, and metadata enrichment. FAISS with metadata filtering.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from dotenv import load_dotenv
load_dotenv()

from ingest_data import load_and_process_documents

_root = Path(__file__).resolve().parent
DOMAIN_DOCS_DIR = Path(os.getenv("DOMAIN_DOCS_DIR", str(_root / "domain_docs")))
FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", str(_root / "faiss_index")))


def build_rag_index() -> FAISS | None:
    """Build FAISS index from domain docs (via ingest_data). Call once at startup if index missing."""
    chunks = load_and_process_documents()
    if not chunks:
        return None
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return FAISS.from_documents(chunks, embeddings)


def get_vectorstore() -> FAISS | None:
    """Return FAISS vectorstore. Builds index if needed."""
    if FAISS_INDEX_PATH.exists():
        try:
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            return FAISS.load_local(str(FAISS_INDEX_PATH), embeddings, allow_dangerous_deserialization=True)
        except Exception:
            pass
    vs = build_rag_index()
    if vs:
        FAISS_INDEX_PATH.mkdir(parents=True, exist_ok=True)
        vs.save_local(str(FAISS_INDEX_PATH))
    return vs


def retrieve_from_knowledge_base(
    query: str,
    k: int = 4,
    filter_dict: Optional[dict] = None,
) -> list[dict]:
    """
    Retrieve relevant chunks from domain knowledge base.
    filter_dict: Optional metadata filter (e.g. {"doc_type": "guidelines"}).
    Returns list of dicts with page_content and metadata.
    """
    try:
        vs = get_vectorstore()
        if vs is None:
            return []
        kwargs = {"k": k}
        if filter_dict:
            kwargs["filter"] = filter_dict
        docs = vs.similarity_search(query, **kwargs)
        return [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]
    except Exception:
        return []

"""
Lab 2: Project-Specific Ingestion & Cleaning
Processes domain docs with cleaning and metadata enrichment (>=3 searchable tags per chunk).
"""
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

DOMAIN_DOCS_DIR = Path(__file__).parent / "domain_docs"


def _clean_text(text: str) -> str:
    """Strip domain-specific noise: HTML tags, excessive whitespace, common headers/footers."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse excessive whitespace
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    return text.strip()


def _get_doc_metadata(file_path: Path) -> dict:
    """Infer metadata from file path and stats. Returns >=3 searchable tags."""
    name = file_path.stem.lower()
    # doc_type: guidelines, style, structure, etc.
    doc_type = "guidelines" if "guideline" in name else ("style" if "style" in name else "reference")
    # department: content team
    department = "content"
    # priority_level: high for guidelines
    priority_level = "high" if doc_type == "guidelines" else "medium"
    # last_updated: from file mtime
    try:
        mtime = file_path.stat().st_mtime
        last_updated = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        last_updated = datetime.now().strftime("%Y-%m-%d")
    return {
        "doc_type": doc_type,
        "department": department,
        "priority_level": priority_level,
        "last_updated": last_updated,
    }


def load_and_process_documents() -> list[Document]:
    """
    Load domain docs, clean, enrich with metadata (>=3 tags), and chunk.
    Returns List[Document] ready for embedding and indexing.
    """
    loader = DirectoryLoader(
        str(DOMAIN_DOCS_DIR),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    raw_docs = loader.load()
    base_meta = {"doc_type": "guidelines", "department": "content", "priority_level": "high", "last_updated": datetime.now().strftime("%Y-%m-%d")}

    cleaned_docs = []
    for d in raw_docs:
        content = _clean_text(d.page_content)
        if not content:
            continue
        source = d.metadata.get("source", "")
        try:
            file_path = Path(source)
            meta = _get_doc_metadata(file_path)
        except Exception:
            meta = base_meta.copy()
        meta["source"] = source
        cleaned_docs.append(Document(page_content=content, metadata=meta))

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    chunks = splitter.split_documents(cleaned_docs)
    # Ensure each chunk has >=3 searchable tags
    for c in chunks:
        if "doc_type" not in c.metadata:
            c.metadata.setdefault("doc_type", "guidelines")
        if "department" not in c.metadata:
            c.metadata.setdefault("department", "content")
        if "priority_level" not in c.metadata:
            c.metadata.setdefault("priority_level", "high")
        if "last_updated" not in c.metadata:
            c.metadata.setdefault("last_updated", datetime.now().strftime("%Y-%m-%d"))
    return chunks


if __name__ == "__main__":
    chunks = load_and_process_documents()
    print(f"Processed {len(chunks)} chunks")
    if chunks:
        print("Sample metadata:", chunks[0].metadata)

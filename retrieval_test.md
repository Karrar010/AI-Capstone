# Retrieval Test Results (Lab 2)

Run `python run_retrieval_tests.py` to regenerate this file with live results from the FAISS index.

## Test 1: General semantic search

**Query:** How should I structure a technical blog post?

*(Results appear after running run_retrieval_tests.py)*

---

## Test 2: Citation and formatting guidance

**Query:** How do I cite sources in a blog?

*(Results appear after running run_retrieval_tests.py)*

---

## Test 3: Metadata filtering (doc_type=guidelines only)

**Query:** Blog writing guidelines  
**Filter:** `{"doc_type": "guidelines"}`  
*Demonstrates retrieval restricted to documents with doc_type=guidelines.*

*(Results appear after running run_retrieval_tests.py)*

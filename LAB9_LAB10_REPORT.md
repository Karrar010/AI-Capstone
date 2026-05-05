# Lab 9 & Lab 10: Industrial Packaging, Deployment, and CI Quality Gates

This document satisfies the written-report expectation for both labs: **what** was implemented, **why** those choices were made, and **how** to reproduce results. Replace screenshot placeholders with your own captures for submission.

---

## Lab 9 — Container packaging and orchestration

### Reproducible container image (`Dockerfile`)

| Decision | Rationale |
|----------|-----------|
| **Base image: `python:3.12-slim-bookworm`** | Small glibc-based image with reliable PyPI wheels for scientific stack (`numpy`, `faiss-cpu`, `sentence-transformers`). Alpine/musl often breaks binary wheels. Bookworm is a stable Debian generation. |
| **Layer order** | (1) `apt` build deps → (2) `COPY requirements.txt` + `pip install` → (3) `COPY` application source **last**. Edits to application code do not invalidate the heavy dependency layer, so rebuilds stay fast and deterministic given a pinned `requirements.txt`. |
| **Multi-stage** | Not used: a single stage keeps the Dockerfile easier to audit for coursework; image size is acceptable for a lab. A future production build could split a builder stage (compile wheels) from a slimmer runtime. |
| **Non-root user** | `appuser` reduces risk if the API process is compromised. |
| **Runtime dirs** | `FAISS_INDEX_PATH=/data/faiss_index` is backed by a **named volume** in Compose so embeddings/FAISS files can survive API container replacement. |

### Secret-free image

- **No** `COPY .env` and **no** `ARG GROQ_API_KEY` at build time in the Dockerfile.
- At **runtime**, Compose injects `GROQ_API_KEY`, `POSTGRES_PASSWORD`, etc. via **environment variable substitution** from a local `.env` file (Compose loads it automatically) or from the shell (CI).
- `.dockerignore` excludes `.env`, `venv`, local SQLite files, local `faiss_index`, and other caches so they never enter the build context.

### Multi-service orchestration (`docker-compose.yml`)

| Service | Role |
|---------|------|
| **`postgres`** | Backing **checkpoint store** for LangGraph using `langgraph-checkpoint-postgres` + `PostgresSaver`. Data persists in the **`postgres_data`** named volume. |
| **`api`** | **FastAPI** (`uvicorn`). Connects to Postgres with **`POSTGRES_URI=postgresql://…@postgres:5432/…`**. **Service discovery** is standard Docker DNS (`postgres` hostname on the Compose network). Starts after Postgres passes **`healthcheck`**. Stopping: `docker compose down` stops both; `down -v` removes volumes (destructive). |

Environment variable **`POSTGRES_URI`** (set only in Compose for the `api` service) switches **`main.py` lifespan** to Postgres; local laptop runs without it still use SQLite.

### Persistent data (proof outline)

1. `docker compose up --build -d`
2. Call `POST /chat` with a fixed `thread_id` (capture JSON response — screenshot #1).
3. `docker compose restart api` (Postgres volume **keeps** checkpoints).
4. Optionally inspect Postgres:  
   `docker compose exec postgres psql -U bwa -d bwa -c "\dt"`  
   and confirm checkpoint-related tables exist after a run (screenshot #2).
5. Re-invoke with the **same** `thread_id` and optional resume patterns as your course requires (screenshot #3).

### End-to-end verification

- Build: `docker compose build`
- Run: `docker compose up -d`
- Automated smoke: `python scripts/e2e_compose_request.py`
- Manual: `curl` / OpenAPI at `http://127.0.0.1:8000/docs` (screenshot #4)

---

## Lab 10 — Automated quality gate and thresholds

### `run_eval.py` (CI-ready)

- **Headless**: runs `lab7_eval.py` as a subprocess (no prompts).
- **Credentials**: **`GROQ_API_KEY` required** in the environment; never read from committed files.
- **Exit codes**: **0** if every metric in `eval_thresholds.json` passes its **`min`**; **1** otherwise (or on subprocess / I/O failure).
- **Artifact**: writes **`ci_eval_results.json`** with `gates[]` entries: `metric`, `score`, `threshold_min`, `pass`, `rationale`.

### `eval_thresholds.json` (versioned)

- Defines at least **two** metrics aligned with Lab 7 averages: **`average_faithfulness`**, **`average_answer_relevancy`**.
- Each includes **`min`** and a short **rationale** plus ±10% intuition in the `rationale` text (see file).

### Pipeline (`.github/workflows/ci.yml`)

- Triggers on **push** to **`main` / `master`** and **`workflow_dispatch`**.
- Steps: checkout → setup Python 3.12 → `pip install -r requirements.txt` → `python run_eval.py`.
- **Secrets**: configure **`GROQ_API_KEY`** in the repo’s **Settings → Secrets and variables → Actions**. Optional **`TAVILY_API_KEY`** for richer eval rows.
- On completion, uploads **`ci_eval_results.json`** and **`ci_eval_raw.json`** as workflow **artifacts** (pass or fail).

### Breaking-change demonstration (for your viva / screenshots)

1. **Fail CI**: On a throwaway branch, either (A) lower scores by intentionally degrading the agent (e.g. strip RAG context usage in prompts, or add misleading system text), **or** (B) tighten `eval_thresholds.json` beyond what smoke eval achieves. Push and capture a **red** workflow run (screenshot #5).
2. **Restore**: Revert the degradation / thresholds on `main` and push; capture a **green** run (screenshot #6).

---

## Screenshot checklist (paste into your PDF report)

1. `docker compose ps` showing `api` + `postgres` healthy  
2. Successful `docker compose build` log tail  
3. `POST /chat` JSON response (curl or Swagger)  
4. `ci_eval_results.json` snippet showing `"pass": true` for all gates  
5. Intentional failure workflow run (red X)  
6. Restored passing workflow run (green check)

---

## Operational commands (quick reference)

```bash
# Local API with Postgres (recommended for Lab 9)
cp .env.example .env   # then edit secrets
docker compose up --build -d
python scripts/e2e_compose_request.py

# CI gate locally
export GROQ_API_KEY=... 
python run_eval.py

# Teardown (keeps volumes)
docker compose down
```

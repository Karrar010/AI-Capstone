# Setup and API Keys

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Environment Variables (.env)

Create a `.env` file in the project root:

```
# Required for main agent
GROQ_API_KEY=gsk_...

# Required for web research (Tavily)
TAVILY_API_KEY=tvly-...
```

## 3. API Keys You Need

| Key | Purpose | Get it from |
|-----|---------|-------------|
| `GROQ_API_KEY` | LLM (Llama via Groq) | https://console.groq.com |
| `TAVILY_API_KEY` | Web search for research | https://tavily.com |

## 4. Run the Blog Agent

**Use the project virtual environment’s Python** so Streamlit and NumPy come from `venv`, not a global or `AppData\Roaming\Python\...` install. A bare `streamlit` on PATH can pull an experimental MINGW-built NumPy on Windows and spam `RuntimeWarning` in `numpy.core.getlimits`.

**PowerShell (recommended on Windows):**

```powershell
.\run_frontend.ps1
```

Or explicitly:

```powershell
.\venv\Scripts\python.exe -m streamlit run bwa_frontend.py
```

After `.\venv\Scripts\Activate.ps1`:

```powershell
python -m streamlit run bwa_frontend.py
```

**macOS / Linux:**

```bash
source venv/bin/activate
python -m streamlit run bwa_frontend.py
```

**Check NumPy is from the venv:**

```powershell
.\venv\Scripts\python.exe -c "import numpy; print(numpy.__file__)"
```

The path should contain `venv\Lib\site-packages` (Windows) or `venv/lib/python.../site-packages` (Unix).

### If NumPy warnings persist

Recreate the venv from [official CPython](https://www.python.org/downloads/) (or conda), reinstall deps, then run via `python -m streamlit` as above:

```powershell
Remove-Item -Recurse -Force .\venv
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -U pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_frontend.ps1
```

## 5. Run MCP Pipeline (Part B)

Uses HTTP transport (avoids Windows stdio issues). Run server and client in **two separate terminals**:

**Terminal 1 – MCP Server** (keep this running):

```bash
cd mcp_pipeline
python mcp_server.py
```

**Terminal 2 – MCP Client**:

```bash
cd mcp_pipeline
python mcp_client.py
```

The client connects to http://127.0.0.1:8000/mcp, discovers tools, and executes `word_count`.

## 6. Optional: RAG Index

The RAG pipeline builds the FAISS index on first run. Domain docs are in `domain_docs/`. Add `.txt` files to expand the knowledge base.

## 7. Lab Scripts

- **Retrieval tests (Lab 2):** `python run_retrieval_tests.py` — rebuilds index, runs 3 test queries, writes `retrieval_test.md`
- **Persistence test (Lab 5):** Run `python persistence_test.py 1`, then in a new terminal `python persistence_test.py 2` — proves session recovery via `checkpoint_db.sqlite`
- **Security smoke (Lab 6):** `python lab6_guardrail_smoke.py`
- **Evaluation (Lab 7):** `python lab7_eval.py` — see §8

## 8. Lab 7: LangSmith tracing and RAGAS evaluation

Add to `.env` (optional but required for traces in LangSmith):

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=bwa-lab7
```

Create a project in [LangSmith](https://smith.langchain.com) and use the API key from your workspace settings. Traces appear when you run Streamlit, `lab7_eval.py`, or any code path that invokes the compiled LangGraph with these variables set.

**Gold dataset:** [`test_dataset.json`](test_dataset.json) (22 blog topics + reference answers + expected tools).

**Run RAGAS + tool accuracy (no `.md` files written; uses in-memory checkpointer):**

```powershell
$env:BWA_EVAL_SKIP_SAVE = "1"
$env:BWA_LLM_GUARD = "0"
.\venv\Scripts\python.exe lab7_eval.py --limit 5
```

Omit `--limit` to score all rows (slow and API-heavy). Results print to stdout and save to `lab7_ragas_results.json`.

**Complex topics for trace review:** paste lines from [`lab7_complex_queries.txt`](lab7_complex_queries.txt) into the Streamlit **Topic** field while tracing is enabled, then inspect latency per node in the LangSmith run.

**Submission files:** fill [`evaluation_report.md`](evaluation_report.md) from `lab7_ragas_results.json`, paste your project/trace URL into [`observability_link.txt`](observability_link.txt), and complete [`bottleneck_analysis.txt`](bottleneck_analysis.txt) after reviewing traces.

## 9. Lab 8: FastAPI + streaming (LangGraph over HTTP)

- **Schemas:** [`schema.py`](schema.py) — `ChatRequest` (`message`, `thread_id`), `ChatResponse` (`final_answer`, `status`).
- **App:** [`main.py`](main.py) — `POST /chat` (JSON response), `POST /stream` (SSE via `graph.astream`), `GET /health`. The checkpointer is opened once in FastAPI **lifespan**: **Postgres** when `POSTGRES_URI` is set (Docker Compose), otherwise **SQLite** at `CHECKPOINT_SQLITE_PATH`.

**Run locally (venv, no Docker):**

```powershell
.\venv\Scripts\Activate.ps1
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/docs`. Example: `POST /chat` with body `{"message":"Write a short paragraph about renewable energy.","thread_id":"demo-1"}`.

## 10. Lab 9 — Docker / Compose & Lab 10 — CI gate

- **Report:** [`LAB9_LAB10_REPORT.md`](LAB9_LAB10_REPORT.md) — container rationale, secrets, persistence proof, CI + breaking-change demo instructions.
- **Image:** [`Dockerfile`](Dockerfile) — build with `docker compose build`.
- **Orchestration:** [`docker-compose.yml`](docker-compose.yml) — services **`api`** + **`postgres`**; volumes **`postgres_data`** (checkpoints) and **`faiss_data`** (FAISS index). Copy [`.env.example`](.env.example) → `.env` and set **`GROQ_API_KEY`**, **`POSTGRES_PASSWORD`** (never commit `.env`).
- **One-command stack:** `docker compose up --build -d` — then `http://127.0.0.1:8000/docs` or `python scripts/e2e_compose_request.py`.
- **CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — on push to `main`, runs [`run_eval.py`](run_eval.py) using [`eval_thresholds.json`](eval_thresholds.json). Add repo secret **`GROQ_API_KEY`**.
- **Local gate:** `python run_eval.py` (requires `GROQ_API_KEY`; optional `CI_EVAL_LIMIT`).

**Stop stack:** `docker compose down` (add `-v` to delete volumes).

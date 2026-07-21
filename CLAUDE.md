# CLAUDE.md

## Project
We are rebuilding the architecture from
https://github.com/jamwithai/production-agentic-rag-course (the "arXiv Paper
Curator" — a 7-week production agentic RAG course) as a portfolio project for
AI Engineer job applications.

This is a REBUILD, not a fork or clone. I (the user) need to understand every
architectural decision deeply enough to defend it in interviews — so implement
nothing without first explaining the approach and getting my approval.

## Reference project — what we're keeping from it
- Domain: arXiv papers
- Keyword-search-first philosophy: BM25 before vector/embedding search
- Hybrid search via Reciprocal Rank Fusion (RRF), combining keyword + vector results
- Agentic RAG pattern via LangGraph, same node structure:
  guardrail -> retrieve -> grade -> rewrite -> generate
- Langfuse for observability/tracing on every pipeline call
- Redis for caching repeated queries
- Docker for containerization
- FastAPI backend

## Deliberate changes from the reference project (and why)
| Reference project | Our change | Reason |
|---|---|---|
| OpenSearch (BM25 + hosting cluster) | `rank_bm25` (pure Python, in-process) | Avoid running/maintaining a search cluster for a single-user portfolio project |
| PostgreSQL (paper metadata) | SQLite | Zero-setup, file-based, sufficient at this scale |
| Apache Airflow (ingestion DAGs) | Simple Python script, manually or cron-triggered | No need for a DAG scheduler without recurring, multi-pipeline orchestration at scale |
| Ollama (local LLM for dev) | API only (Claude/OpenAI), no local LLM | Simpler setup; matches what we deploy with anyway, so no need to maintain two code paths |
| Gradio (frontend) | Streamlit (chat page with inline expandable trace + upload/status page) | More layout control; trace shown inline rather than as a separate page to reduce build time |
| Separate BM25 phase then hybrid phase | Merged into a single search phase | Both pieces are built and compared together to save time, without losing the comparison table |
| Telegram bot integration | Removed entirely | Low signal for an AI engineer role; adds integration complexity with no evaluation value |
| No published evaluation harness | Custom eval: retrieval precision/recall, routing/guardrail accuracy, answer faithfulness (naive vs. agentic RAG comparison) | This is our main original contribution and differentiator |
| Not featured | `slowapi` rate limiting on public endpoints + backoff/retry on the arXiv API client | Realistic production concern (LLM-backed endpoints cost money; arXiv enforces its own rate limits) |

Langfuse (observability) and Redis (caching) are KEPT as-is from the reference
project — these are our strongest production-signal components and are not
being simplified further.

Known limitation to state proactively, not hide: `rank_bm25` and SQLite don't
scale past a small/medium corpus held in memory. This is an accepted, explicit
trade-off for project scope — not an oversight. If asked, the answer is: "at
scale I'd move BM25 to OpenSearch/Elasticsearch and metadata to Postgres; the
RRF fusion logic and agentic nodes wouldn't change."

## Phases (specs/01 through specs/07)
1. Infra skeleton
2. Ingestion pipeline
3. Search: BM25 + hybrid RRF (built and compared together, one phase)
4. Agentic nodes (guardrail -> retrieve -> grade -> rewrite -> generate)
5. Observability + caching (Langfuse + Redis + slowapi rate limiting)
6. Streamlit frontend (chat with inline trace + upload/status page)
7. Evaluation harness + deploy + README polish

## Spec format (one file per phase, in /specs/)
Each phase gets ONE spec file: `specs/0X-phase-name.md`. Before writing any
code for a phase, write this file and get my approval. It must contain these
sections, in this order:

1. **What's this?** — plain-language description of what the phase builds.
2. **Why this?** — why the phase is needed, what it unlocks for later phases.
3. **Options I had** — the realistic alternatives considered (frameworks,
   patterns, infra choices).
4. **Why I chose what I chose** — the actual reasoning for the decision made.
5. **Possible approaches & trade-offs** — a table: approach | trade-off,
   covering both the chosen approach and the rejected ones.
6. **Common failure stories & fixes** - generate them, even if you dont hit,possible common ones
The goal of this format: I must be able to defend every phase in an
interview — what it is, why it exists, what else I considered, why I chose
what I chose, and a real failure/fix story. Do not proceed to implementation
until sections 1-5 are written and I've approved them.

## Workflow rules
- SPEC-DRIVEN DEVELOPMENT: write the phase's spec file (sections 1-5 above)
  before any code. Do not write code until I approve the spec.
- Once approved, break the spec into a short task checklist (in the same
  spec file or a `## Tasks` section at the end) and implement one task at a
  time, pausing for my review after each.
- After the phase is implemented, fill in "Common failure stories & fixes"
  in the spec with what we actually hit and how we solved it.
- After each phase, append a summary to DECISIONS.md: what we built, what
  alternatives we considered, why we chose what we chose.
- Before moving to the next phase, quiz me with 3-5 interview-style questions
  about what we just built, so I can check my own understanding.

## Tech stack
Python 3.12, uv, FastAPI, LangGraph, Qdrant, rank_bm25 + RRF fusion, SQLite,
Claude API or OpenAI API (LLM, swappable via env var, no local LLM),
sentence-transformers or Jina (embeddings), Redis, Langfuse, slowapi,
Streamlit, Docker Compose (app + Qdrant + Redis only), Pytest, Ruff, MyPy,
pre-commit.

## Commands
- `make start` — docker compose up
- `uv run pytest` — run tests
- `make lint` — ruff + mypy
- `uv run python -m src.ingest` — run arXiv ingestion
- `uv run streamlit run streamlit_app/Home.py` — run the frontend

## Code style
- Type hints required on all functions
- Pydantic models for all API request/response schemas
- No inline SQL — use the repository pattern in src/db/

## Project structure
```
src/routers/       - API endpoints
src/services/      - business logic (ingestion, search, agents, cache)
src/models/        - DB models
src/agents/        - LangGraph nodes (guardrail, retrieve, grade, rewrite, generate)
streamlit_app/     - Streamlit frontend: chat page (reasoning trace shown inline,
                     expandable, not a separate page) + upload/status page.
                     Thin client only, calls FastAPI, no business logic.
specs/             - one defense-spec file per phase: specs/0X-phase-name.md
                     (what's this / why this / options / why chosen /
                     trade-offs / failure stories & fixes / tasks)
DECISIONS.md       - running log of architectural decisions + alternatives considered
```

## Constraints
- Keep infra to Docker Compose only, max 3 services (app, Qdrant, Redis) —
  no Kubernetes, no Airflow, no OpenSearch.
- Never commit .env or API keys.
- Do not add services or dependencies not listed in the tech stack above
  without discussing trade-offs with me first.
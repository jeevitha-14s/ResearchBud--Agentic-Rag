# ArXiv Paper Curator

> **An agentic Retrieval-Augmented Generation system for searching and reasoning over arXiv papers — hybrid retrieval, iterative self-correction, and a production-inspired evaluation harness, built end to end.**

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-1C3C3C)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector_Search-DC244C)
![Redis](https://img.shields.io/badge/Redis-Caching-DC382D)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Langfuse](https://img.shields.io/badge/Langfuse-Observability-6C47FF)

---

## Overview

Most RAG demos retrieve once and generate immediately. **ArXiv Paper Curator** treats retrieval as something to be checked, not trusted: a **LangGraph-powered agent** grades the context it retrieves, rewrites the query when the evidence is weak, and refuses to answer when there still isn't enough support — instead of generating a fluent guess.

The system continuously combines two independent retrieval strategies — **BM25 keyword search** and **dense vector search** — merged via **Reciprocal Rank Fusion**, so exact terminology (equations, author names, paper titles) and paraphrased natural-language questions are both handled well.

When a query comes in, the agent:

1. Screens it with a guardrail (in-scope vs. off-topic / unsafe).
2. Retrieves via hybrid BM25 + vector search.
3. Grades whether the retrieved context actually supports an answer.
4. Rewrites the query and retries if the evidence is insufficient (bounded retries).
5. Generates a grounded, cited answer — or refuses, if no version of the query surfaces enough evidence.

---

## Features

### Hybrid Retrieval
* BM25 keyword search (`rank_bm25`, in-process)
* Dense vector search (Qdrant + sentence-transformer embeddings)
* Reciprocal Rank Fusion to merge both result sets

### Agentic RAG Workflow
* Query guardrail
* Hybrid retrieval
* Context grading
* Bounded query rewriting
* Evidence-based, cited response generation

### arXiv Paper Ingestion
* Metadata + PDF fetch directly from the arXiv API (with retry/backoff)
* PDF text extraction and paragraph-aware chunking
* Embedding generation
* Idempotent ingestion — re-running skips papers already ingested by arXiv ID

### Production-Oriented Infrastructure
* FastAPI backend
* Streamlit frontend (chat + upload/status)
* Redis response caching
* Langfuse tracing on every pipeline call
* Docker Compose deployment (app + Qdrant + Redis)
* Rate limiting (`slowapi`) on public endpoints
* Typed configuration (`pydantic-settings`)
* 100+ tests, no live API calls in CI path

---

## Architecture

```text
                +----------------------+
                |      arXiv API       |
                +----------+-----------+
                           |
                    Paper Ingestion
                           |
             PDF Extraction & Chunking
                           |
        +------------------+------------------+
        |                                     |
    SQLite Metadata                  Qdrant Vector Store
        |                                     |
        +------------------+------------------+
                           |
                     Hybrid Retrieval
              (BM25 + Vector + RRF Fusion)
                           |
                   LangGraph Agent Workflow
                           |
                       Guardrail
                           |
                        Retrieve
                           |
                     Grade Context
                           |
                Rewrite Query (if needed)
                           |
                    Generate Answer
                           |
                     FastAPI Backend
                           |
                 Streamlit Web Interface
```

---

## Agent Workflow

The retrieval pipeline is modeled as an explicit state machine in LangGraph, not a single prompt call:

```text
User Query
      │
      ▼
  Guardrail
      │
      ▼
Hybrid Retrieval
      │
      ▼
Context Grading
      │
      ├─────────────────┐
      ▼                 │
Enough Evidence?         │
      │                  │
   Yes│              No  │
      ▼                  ▼
Generate Answer     Rewrite Query
                          │
                          ▼
                    Retrieve Again
```

The rewrite loop is bounded to prevent infinite retries.

---

## Hybrid Search

| Strategy | Mechanism | Best for |
|---|---|---|
| **BM25** | Keyword term matching (`rank_bm25`) | Exact terminology, equations, author names, paper titles |
| **Dense Vector Search** | Sentence-embedding similarity (Qdrant) | Paraphrased questions, conceptual/semantic similarity |
| **Reciprocal Rank Fusion** | Rank-based merge of both result sets | Avoids score-normalization mismatches between the two methods |

---

## Tech Stack

| Category | Technologies |
|---|---|
| Backend | Python 3.12, FastAPI, LangGraph |
| Retrieval | Qdrant, rank_bm25, Sentence Transformers, Reciprocal Rank Fusion |
| Storage | SQLite, Redis |
| LLM | Anthropic Claude or OpenAI (swappable via env var) |
| Observability | Langfuse |
| Frontend | Streamlit |
| Tooling | Docker Compose, Pytest, Ruff, MyPy, pre-commit |

---

## Project Structure

```text
src/
├── agents/       # LangGraph nodes: guardrail, retrieve, grade, rewrite, generate
├── db/           # Repository pattern — no inline SQL elsewhere
├── eval/         # Retrieval, guardrail, and faithfulness evaluation
├── models/       # Pydantic request/response schemas
├── routers/      # FastAPI endpoints
├── services/     # Ingestion, search, caching business logic

streamlit_app/    # Thin client: chat (inline trace) + upload/status pages

tests/
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/chat` | Agentic RAG chat |
| POST | `/search` | Hybrid search |
| GET | `/papers` | List indexed papers |
| POST | `/ingest` | Ingest arXiv papers |
| POST | `/reindex` | Rebuild BM25 + vector indexes from all ingested chunks |

---

## Evaluation

A custom evaluation harness measures retrieval quality, guardrail accuracy, and answer faithfulness — comparing the agentic pipeline against a naive single-shot retrieve-then-generate baseline that shares the exact same generation prompt, so the comparison isolates one variable: presence of guardrail/grade/rewrite.

Run it against the real ingested corpus and a real LLM:

```bash
uv run python -m src.evaluate
```

### Real numbers from a live run

| Metric | Result |
|---|---|
| Retrieval precision (mean) | 0.82 (9 queries, 3 papers) |
| Retrieval recall (mean) | 1.00 (9 queries, 3 papers) |
| Guardrail accuracy | 100% (8 queries) |

**Faithfulness by category — naive RAG vs. agentic RAG**

| Category | Naive answer rate | Naive faithfulness | Agentic answer rate | Agentic faithfulness |
|---|---|---|---|---|
| In-corpus | 100% | 4.50 | 50% | 4.00 |
| Out-of-corpus | 100% | 5.00 | 0% | n/a |
| Off-topic | 100% | 5.00 | 0% | n/a |

---

## Running Locally

### Clone

```bash
git clone https://github.com/jeevitha-14s/Agentic-arxiv-rag.git
cd Agentic-arxiv-rag
```

### Configure Environment

```bash
cp .env.example .env
```

`.env.example` documents every variable:

```env
APP_ENV=dev
QDRANT_HOST=qdrant
QDRANT_PORT=6333
REDIS_HOST=redis
REDIS_PORT=6379

# "anthropic" or "openai" — only the matching key below is used
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-5
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Optional — leave blank to run with tracing silently disabled
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Start Services

```bash
docker compose up --build
```

Services: FastAPI · Qdrant · Redis

### Launch Frontend

```bash
streamlit run streamlit_app/Home.py
```

---

## Testing

```bash
pytest           # 102 tests — LLM/embedding calls mocked or in-memory, no live API calls
ruff check .
mypy src
```

---


## Key Learnings

This project demonstrates practical experience with:

* Agentic system design (LangGraph state machines, bounded self-correction loops)
* Hybrid information retrieval (BM25, dense vectors, rank fusion)
* RAG evaluation methodology (precision/recall, LLM-as-judge faithfulness, naive-vs-agentic comparison)
* Production-adjacent concerns: observability (Langfuse), caching (Redis), rate limiting, typed configuration
* Deliberate, documented trade-offs between prototype scope and production scale

# 📚 ArXiv Paper Curator

An end-to-end **Agentic Retrieval-Augmented Generation (RAG)** system for searching and interacting with arXiv research papers using hybrid retrieval, iterative reasoning, and production-inspired architecture.

Unlike traditional RAG systems that retrieve once and generate immediately, this project uses a **LangGraph-powered agent** that evaluates retrieved context, rewrites ambiguous queries when necessary, and only answers when sufficient supporting evidence exists.

---

## ✨ Features

* 🔍 Hybrid Retrieval

  * BM25 keyword search
  * Dense vector search using Qdrant
  * Reciprocal Rank Fusion (RRF)

* 🤖 Agentic RAG Workflow

  * Query guardrail
  * Hybrid retrieval
  * Context grading
  * Query rewriting
  * Evidence-based response generation

* 📄 arXiv Paper Ingestion

  * Fetch metadata directly from arXiv
  * Download and parse PDFs
  * Automatic chunking
  * Embedding generation
  * Incremental indexing

* 📊 Production-Oriented Infrastructure

  * FastAPI backend
  * Streamlit frontend
  * Redis response caching
  * Langfuse observability
  * Docker Compose deployment
  * Rate limiting
  * Retry & backoff
  * Typed configuration
  * Comprehensive testing

---

# Architecture

```
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
          ↓
     Retrieve
          ↓
      Grade Context
          ↓
  Rewrite Query (if needed)
          ↓
     Generate Answer
                           |
                     FastAPI Backend
                           |
                 Streamlit Web Interface
```

---

# Tech Stack

### Backend

* Python 3.12
* FastAPI
* LangGraph

### Retrieval

* Qdrant
* rank_bm25
* Sentence Transformers
* Reciprocal Rank Fusion (RRF)

### Storage

* SQLite
* Redis

### LLM

* Anthropic Claude
* OpenAI (configurable)

### Observability

* Langfuse

### Frontend

* Streamlit

### Tooling

* Docker Compose
* Pytest
* Ruff
* MyPy
* pre-commit

---

# Agent Workflow

The retrieval pipeline is modeled as a state machine using LangGraph.

```
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
      ├─────────────┐
      │             │
      ▼             │
Enough Evidence?    │
      │             │
   Yes│             │No
      ▼             │
Generate Answer     │
                    ▼
             Rewrite Query
                    │
                    ▼
               Retrieve Again
```

The rewrite loop is bounded to prevent infinite retries.

---

# Hybrid Search

The retrieval layer combines two complementary search strategies.

### BM25

Efficient keyword-based retrieval.

Ideal for:

* exact terminology
* equations
* author names
* paper titles

---

### Dense Vector Search

Semantic similarity search using sentence embeddings stored in Qdrant.

Ideal for:

* paraphrased questions
* conceptual similarity
* natural language queries

---

### Reciprocal Rank Fusion

Results from BM25 and vector retrieval are merged using RRF.

This avoids score normalization issues while leveraging the strengths of both retrieval methods.

---

# Project Structure

```
src/
├── agents/
├── db/
├── eval/
├── models/
├── routers/
├── services/

streamlit_app/

tests/
```

---

# API Endpoints

| Method | Endpoint   | Description             |
| ------ | ---------- | ----------------------- |
| GET    | `/health`  | Health check            |
| POST   | `/chat`    | Agentic RAG chat        |
| POST   | `/search`  | Hybrid search           |
| GET    | `/papers`  | List indexed papers     |
| POST   | `/ingest`  | Ingest arXiv papers     |
| POST   | `/reindex` | Rebuild retrieval index |

---

# Evaluation

The project includes an evaluation framework for measuring retrieval quality and response behavior.

Evaluated components include:

* Retrieval Precision@K
* Retrieval Recall@K
* Guardrail Accuracy
* Naive RAG vs Agentic RAG
* Faithfulness
* Answer Rate

The evaluation pipeline enables systematic comparison between traditional retrieval and the agentic workflow.

Run it against the real ingested corpus and a real LLM:

```bash
uv run python -m src.evaluate
```

### Real numbers from a live run

```
Retrieval:  mean precision 0.82, mean recall 1.00 (9 queries, 3 papers)
Guardrail:  100% accuracy (8 queries)

Faithfulness, per category (answer_rate / mean_faithfulness):
  in_corpus:      naive 100% / 4.50    agentic  50% / 4.00
  out_of_corpus:  naive 100% / 5.00    agentic   0% / n/a
  off_topic:      naive 100% / 5.00    agentic   0% / n/a
```

The headline finding isn't the faithfulness *score* — naive RAG scores
respectably even on questions it shouldn't answer, because the same system
prompt nudges it to admit uncertainty in prose. The finding is the **answer
rate**: agentic RAG structurally refuses 100% of out-of-corpus and
off-topic questions before generation ever runs (guardrail rejection, or
grading filtering out every retrieved chunk) — a guarantee, not a hope.
Naive RAG's "refusal" on those same questions is voluntary LLM behavior
with no structural backing, and isn't guaranteed to happen on a different
run or a different model. The trade-off: the guardrail also false-rejected
one legitimate in-corpus question in this run, dropping agentic RAG's
in-corpus answer rate to 50%.

---

# Production Readiness

This ships as a documented, runnable Docker Compose stack, not a live
hosted deployment — provisioning and paying for a public cloud VM is a
decision left to whoever deploys this, not made unilaterally here.

What's already in place:

* **Secrets**: read from `.env` (gitignored), never hardcoded; `.env.example`
  documents every required/optional variable with no real values.
* **Health checks**: `app` and `redis` have Compose healthchecks; `app`'s
  startup waits on `redis` being healthy.
* **Restart policy**: all three services run `restart: unless-stopped`.

Known gaps if deploying this for real (deliberately left open, not
overlooked):

* `app`'s `uvicorn --reload` and the bind-mounted `./src` volume are dev
  conveniences — a production image should drop `--reload` and rely on the
  image's baked-in `COPY . .` layer instead of the live-reload mount.
* `qdrant` has no Compose healthcheck (its image ships no `curl`/`wget`),
  so `depends_on` for it is `service_started`, not `service_healthy` — a
  real deployment should probe its REST port from outside the container.
* No resource limits (`mem_limit`/`cpus`) are set on any service.
* No TLS termination — this assumes a reverse proxy (e.g. Caddy/nginx) or a
  managed platform's ingress handles HTTPS in front of `app`.

---

# Running Locally

## Clone

```bash
git clone https://github.com/jeevitha-14s/ResearchRAG.git

cd ResearchRAG
```

---

## Configure Environment

```bash
cp .env.example .env
```

Configure (`.env.example` documents every variable):

```
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

---

## Start Services

```bash
docker compose up --build
```

Services:

* FastAPI
* Qdrant
* Redis

---

## Launch Frontend

```bash
streamlit run streamlit_app/Home.py
```

---

# Testing

Run the test suite (102 tests, no live API calls — LLM/embedding calls are
mocked or use in-memory Qdrant):

```bash
pytest
```

Static analysis:

```bash
ruff check .

mypy src
```

---

# Future Improvements

* Elasticsearch/OpenSearch for large-scale BM25 indexing
* PostgreSQL metadata storage
* Background ingestion workers
* Asynchronous document processing
* Multi-user authentication
* Incremental vector updates
* Streaming LLM responses
* Kubernetes deployment
* CI/CD pipeline
* Advanced retrieval evaluation datasets

---

# Key Design Decisions

* Hybrid retrieval instead of vector-only search
* Rank fusion instead of weighted score normalization
* Agentic retrieval with iterative refinement
* SQLite for lightweight metadata storage
* Redis for response caching
* Provider-agnostic LLM interface
* LangGraph for explicit reasoning flow
* Dockerized deployment for reproducibility

---

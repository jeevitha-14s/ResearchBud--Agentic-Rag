# Architectural Decisions Log

Running log of what was built each phase, what alternatives were considered,
and why the chosen approach won. Full detail for each phase lives in
`specs/0X-phase-name.md`; this is the condensed version.

## Phase 1: Infra Skeleton

**What we built:** Project scaffolding with no domain logic — `src/` package
layout (routers/services/models/agents), a FastAPI app exposing `GET /health`,
`pydantic-settings`-based config, Docker Compose running all three services
(`app`, `qdrant`, `redis`) from day one, Ruff + MyPy + pre-commit for local
quality gates, pytest with one smoke test, and a `Makefile` wrapping the
common commands.

**Alternatives considered:**
- Poetry / pip+requirements.txt instead of `uv` for dependency management.
- Flat module layout instead of `src/`.
- Running the FastAPI app on the host during dev (only Qdrant/Redis
  containerized) instead of the full stack in Compose.
- CI-only lint/type checks instead of local pre-commit hooks.
- Plain `os.environ` reads instead of `pydantic-settings`.

**Why we chose what we chose:**
- `uv`: fastest resolver/installer, single binary, no separate shell
  activation ceremony, and it's the tech stack CLAUDE.md already committed
  to.
- `src/` layout: avoids the classic pytest footgun of silently importing an
  installed copy of the package instead of the local checkout.
- Full stack in Compose from day one: forces app↔Qdrant↔Redis networking to
  be container-correct immediately, instead of deferring that risk to a
  later phase where it's more disruptive to debug.
- pre-commit hooks: for a solo project with no PR reviewer, local
  enforcement is the only gate that reliably runs — CI-only checks are easy
  to ignore.
- `pydantic-settings`: type-safe, validated config, and it's already the
  natural choice since Pydantic is mandated elsewhere for request/response
  schemas — one validation library, not two.

**Real problems hit:** see "Common failure stories & fixes" in
`specs/01-infra-skeleton.md` — Python version drift (`>=3.12` resolved to
3.13 until pinned via `.python-version`), `pre-commit install` requiring a
git repo that didn't exist yet, missing `curl` in the slim Docker base image
breaking the healthcheck, and `docker-compose.yml` referencing a
gitignored `.env` that doesn't exist by default (fixed with `required: false`).

## Phase 2: Ingestion Pipeline

**What we built:** arXiv API client (Atom XML parsing, hand-rolled
retry/backoff), PDF downloader + text extractor (`pdfplumber`), a
paragraph-aware fixed-window chunker with overlap, SQLite storage via a
repository layer (`papers` + `chunks` tables, no inline SQL outside
`src/db/`), and an idempotent orchestration script (`src/ingest.py`,
`--force` to re-ingest). 19 tests covering the client (mocked HTTP),
chunker, repository, and ingestion orchestration (mocked I/O), plus a live
smoke test against the real arXiv API.

**New dependencies added (flagged per CLAUDE.md's constraint on new deps):**
`httpx` (promoted from dev-only to a runtime dependency) and `pdfplumber`.

**Alternatives considered:**
- PyMuPDF or `docling` instead of `pdfplumber` for PDF text extraction.
- `langchain-text-splitters` or a tokenizer-aware splitter instead of a
  hand-rolled chunker.
- `tenacity`/`backoff` instead of a hand-rolled retry decorator.
- Chunking during the search/indexing phase instead of during ingestion.
- Full re-ingest or content-hash change detection instead of
  skip-by-arxiv-id idempotency.

**Why we chose what we chose:**
- `pdfplumber`: MIT license (PyMuPDF is AGPL/commercial — friction for a
  public repo), pure Python (no OCR/torch like `docling`), and arXiv PDFs
  are almost all born-digital so OCR isn't needed.
- Hand-rolled chunker and retry/backoff: both are small enough (~15-30
  lines) that a dependency isn't worth it, and hand-rolled logic is more
  defensible line-by-line in an interview than "I called a library."
  Matches the project's existing pattern of small hand-rolled pieces over
  heavy frameworks.
- Chunk during ingestion, not search: keeps Phase 3 a pure "index what's
  already chunked" step, and keeps chunk boundaries stable/citable across
  search-index rebuilds.
- Skip-by-arxiv-id idempotency: re-running ingestion shouldn't re-download
  and re-parse PDFs it already has; arXiv already versions changed papers
  via ID suffix, so content-hash detection would add complexity for little
  benefit.

**Real problems hit:** see "Common failure stories & fixes" in
`specs/02-ingestion-pipeline.md` — arXiv's API now redirects `http://` to
`https://`, and `httpx.get()` doesn't follow redirects by default, so the
initial live smoke test failed with a 301 treated as an HTTP error (all
three retries exhausted on the same non-redirect-following request). Fixed
by defaulting to `https://` and adding `follow_redirects=True`. Only the
live smoke test caught this — the mocked unit tests couldn't have, since
they construct their own fake success response.

Second real problem: `make lint` passed but `pre-commit run --all-files`
failed mypy on the same code, because the pre-commit mypy hook runs in its
own isolated environment governed by `additional_dependencies` in
`.pre-commit-config.yaml` — which still only listed Phase 1's dependencies
(`pydantic`, `pydantic-settings`, `fastapi`). Missing `httpx`, `pdfplumber`,
`pytest` there meant mypy silently treated code touching them as untyped
`Any` instead of erroring on missing stubs. Fixed by adding all three to
the hook's dependency list. Every new dependency added to `pyproject.toml`
now needs a matching update there too.

## Phase 3: Search — BM25 + Hybrid RRF

**What we built:** BM25 keyword search (`rank_bm25`, persisted to disk),
vector search (`sentence-transformers` embeddings upserted into Qdrant),
and Reciprocal Rank Fusion combining both into a hybrid ranking — built and
compared together in one phase per CLAUDE.md. Plus a comparison CLI
(`src/search_cli.py`) that prints BM25/vector/hybrid results side by side,
an index-build script (`src/index.py`), and a `GET /search` endpoint. 37
tests total (18 new this phase), all passing; verified live against the
Phase 2 ingested papers through Docker Compose (real embeddings, real
Qdrant, real HTTP request to `/search`).

**Alternatives considered:**
- Jina AI or OpenAI/Claude embeddings APIs instead of local
  `sentence-transformers`.
- Weighted score normalization or a cross-encoder re-ranker instead of RRF.
- Rebuilding the BM25 index in-memory at every app startup instead of
  persisting it to disk.
- Auto-indexing during ingestion instead of a separate `src/index.py` step.

**Why we chose what we chose:**
- `sentence-transformers`: fully offline, no API key or per-call cost,
  deterministic output — worth the `torch`-sized dependency because
  embeddings are this phase's actual value, unlike Phase 2's `docling`
  rejection where a lighter alternative existed.
- RRF over weighted score normalization: BM25 and cosine scores live on
  incomparable scales; RRF only needs rank position, avoiding a fragile
  normalization/weighting hyperparameter to tune and defend.
- Persisted BM25 index + separate `src/index.py`: decouples "add papers"
  (Phase 2) from "pay indexing cost," and avoids re-tokenizing the whole
  corpus on every FastAPI restart.

**Real problems hit:** see "Common failure stories & fixes" in
`specs/03-search-bm25-hybrid-rrf.md` — two, both worth remembering:
1. BM25's IDF formula evaluates to exactly zero when a term appears in
   exactly half the documents of a very small corpus (`N = 2n`), which
   silently dropped a genuinely relevant result past our `score > 0`
   filter. Not a library bug — a real, documented small-corpus edge case,
   directly related to this project's own stated known limitation
   (`rank_bm25`/SQLite don't scale, by design).
2. Adding `sentence-transformers` to the pre-commit mypy hook's
   `additional_dependencies` (the fix that worked fine in Phase 2 for
   lighter packages) made `pre-commit run --all-files` time out after 3+
   minutes — it tried to install `torch` a second time into a fully
   separate isolated environment. Fixed by replacing the `mirrors-mypy`
   repo hook with a `local`/`language: system` hook running
   `uv run mypy src` directly against the project's own venv — one mypy
   environment for the whole project instead of two that can drift or,
   in this case, become impractically slow.

## Phase 4: Agentic Nodes (guardrail → retrieve → grade → rewrite → generate)

**What we built:** a LangGraph `StateGraph` wiring guardrail → retrieve →
grade → rewrite → generate, with conditional routing (off-topic queries
skip straight to a rejection; too-few-relevant-chunks routes to rewrite and
loops back to retrieve, capped at `max_rewrites`). A provider-agnostic
`src/services/llm.py` (Claude or OpenAI, swappable via `LLM_PROVIDER`), a
`POST /chat` endpoint, and `src/agent_cli.py` for terminal testing. 58
tests total (23 new this phase) — node-level unit tests with a fake LLM
client, full-graph routing tests (reject path, rewrite-then-succeed,
rewrite-cap-exhausted), and a mocked `/chat` endpoint test. Verified live
with a real Anthropic API key: correct guardrail accept/reject on real
queries, correct grading (2 of 5 chunks kept on one real query), and a
well-cited final answer over the Phase 2/3 corpus.

**Alternatives considered:**
- Hardcoding one LLM provider instead of a swappable abstraction.
- `claude-opus-4-8` as the default model instead of `claude-sonnet-5`.
- Per-chunk grading (N LLM calls) instead of one batched call.
- An unbounded rewrite loop instead of a hard cap.

**Why we chose what we chose:**
- Provider-agnostic LLM client: CLAUDE.md's tech stack explicitly requires
  "Claude API or OpenAI API... swappable via env var."
- `claude-sonnet-5` default, not Opus: a single query can trigger up to 4
  LLM calls in this graph (guardrail, grade, rewrite, generate) — Sonnet 5
  reaches near-Opus quality on agentic work at a fraction of the cost,
  which is the right trade-off for a multi-call-per-turn pipeline, not a
  single high-stakes call.
- Batched grading over per-chunk: one call seeing all candidates at once is
  cheaper, faster, and lets the model compare candidates against each
  other rather than judging each in isolation.
- Hard-capped rewrite loop: guarantees the graph terminates and bounds
  cost per query on out-of-corpus questions, at the cost of occasionally
  giving up one rewrite early.

**Real problems hit:** see "Common failure stories & fixes" in
`specs/04-agentic-nodes.md` — two, both caught by tests/live runs, not
invented:
1. A designed-in mitigation ("on unparseable grading response, treat all
   chunks as relevant") turned out to be dead code — `_parse_relevant_indices`
   degrades to an empty set on garbage text rather than raising, so the
   `except ValueError/IndexError` branch was structurally unreachable.
   Fixed by deleting the dead code; the natural "zero relevant chunks"
   degradation is actually safer than the originally-designed fallback
   anyway, since it can't inject irrelevant context into the final answer.
2. `pydantic-settings`' `env_file=".env"` only populates its own `Settings`
   object — it never exports into `os.environ`. The `anthropic` SDK's
   zero-arg client resolves credentials from `os.environ` directly, so the
   first live run failed with an authentication error even though the key
   was correctly sitting in `.env`. Fixed by calling `load_dotenv()`
   explicitly in `src/config.py` before `Settings()` is constructed, so
   both our own config and any third-party SDK reading the environment
   directly see the same values.

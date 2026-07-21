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

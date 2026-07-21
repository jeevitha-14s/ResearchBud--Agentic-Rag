# Phase 2: Ingestion Pipeline

## 1. What's this?
The pipeline that turns an arXiv search query into searchable, stored data:
- **arXiv API client** (`src/services/arxiv_client.py`): queries arXiv's
  public Atom XML API for paper metadata (id, title, authors, abstract,
  categories, published date, PDF URL), with retry/backoff and rate-limit
  awareness.
- **PDF downloader + parser** (`src/services/pdf_parser.py`): downloads each
  paper's PDF and extracts its full text.
- **Chunker** (`src/services/chunker.py`): splits full text into overlapping
  passages sized for retrieval.
- **SQLite storage via repository pattern** (`src/db/`): `papers` and
  `chunks` tables, no inline SQL outside the repository layer.
- **Orchestration script** (`src/ingest.py`): ties the above together,
  idempotent per arXiv ID, runnable via `uv run python -m src.ingest`.

Out of scope for this phase: BM25/vector indexing (Phase 3), anything
agentic (Phase 4). This phase's job ends at "papers and their chunks are
sitting in SQLite, ready to be indexed."

## 2. Why this?
Phase 3 (search) needs a corpus to index and Phase 4 (agents) needs
something to retrieve from — neither can be built or meaningfully tested
without real ingested data. Getting metadata, full text, and chunk
boundaries right now means the search phase is purely "build an index over
existing rows," not "also go fix how text was extracted."

## 3. Options I had
**PDF text extraction library:** PyMuPDF (fitz), `pdfplumber`, `pypdf`,
`docling`.

**Chunking approach:** hand-rolled character/paragraph-window splitter vs.
`langchain-text-splitters` vs. token-aware splitting via a tokenizer
library.

**HTTP client:** `httpx` vs. stdlib `urllib.request` vs. `requests`.

**Retry/backoff:** hand-rolled exponential backoff vs. `tenacity` vs.
`backoff` library.

**Metadata storage granularity:** store only paper-level metadata now and
defer chunking to Phase 3, vs. do chunking in this phase so Phase 3 only
has to index already-chunked rows.

**Idempotency strategy:** re-ingest and overwrite every run vs. skip
already-ingested arXiv IDs vs. content-hash-based change detection.

## 4. Why I chose what I chose
- **`pdfplumber`**: MIT license (PyMuPDF is AGPL/commercial — friction for
  a public portfolio repo), pure Python (no heavy compiled/ML dependencies
  like `docling`'s OCR+torch stack), and arXiv PDFs are almost all
  born-digital text (not scanned), so `pdfplumber`'s text-layer extraction
  is sufficient without OCR.
- **Hand-rolled chunker**: a fixed-size character window with overlap,
  breaking on paragraph boundaries where possible, is enough for
  reasonably uniform academic paper text. Avoids pulling in all of
  LangChain's text-splitting module just for one function — matches the
  project's existing pattern of small hand-rolled pieces over heavy
  frameworks (`rank_bm25` instead of a search cluster, raw SQLite instead
  of an ORM).
- **`httpx`**: async-capable if needed later, nicer API than
  `urllib.request`, and it's already pulled in transitively (FastAPI's
  TestClient), so promoting it to a real runtime dependency doesn't add a
  new package to the lock file's dependency tree, just a new direct
  reference to one already present.
- **Hand-rolled retry/backoff**: arXiv's failure modes are simple (timeout,
  5xx, occasional rate-limit); a ~15-line exponential-backoff decorator
  covers it without a new dependency, and it's easier to explain and defend
  line-by-line in an interview than "I called a library."
- **Chunk during ingestion, not search**: search (Phase 3) should be a pure
  "build indices over existing chunks" step. If chunking lived in Phase 3,
  re-running the search phase would silently re-chunk and drift from what
  was actually stored/citable per paper.
- **Idempotent skip-by-arxiv-id**: re-running ingestion (e.g., cron-style,
  or after adding new categories to search) shouldn't re-download and
  re-parse PDFs it already has. A `--force` flag overrides this when a
  paper needs to be refreshed. Full content-hash change detection is
  overkill — arXiv papers are versioned via their ID (e.g., `v2` suffix)
  when they change, so a new version already gets a distinguishable ID.

## 5. Possible approaches & trade-offs
| Approach | Trade-off |
|---|---|
| **`pdfplumber`** (chosen) | Pure Python means slower than PyMuPDF's C extraction on large batches, but MIT license and no heavy ML dependencies. |
| PyMuPDF (fitz) | Faster, very robust extraction, but AGPL/commercial dual license — a real constraint for a public portfolio repo someone might reuse. |
| `docling` | Best-in-class structure extraction (tables, layout), but pulls in OCR + torch — heavy install, slow cold start, overkill for born-digital arXiv PDFs. |
| **Hand-rolled chunker** (chosen) | Cruder than semantic/sentence-aware chunking, but transparent, dependency-free, and easy to defend/tune in an interview. |
| `langchain-text-splitters` | More sophisticated splitting strategies out of the box, but adds a framework dependency for one function's worth of logic. |
| **`httpx`** (chosen) | One more direct dependency declaration, but nicer API and already in the dependency tree transitively. |
| stdlib `urllib.request` | Zero new dependencies, but clunkier API for headers/timeouts/streaming downloads. |
| **Hand-rolled backoff** (chosen) | Have to get retry/jitter logic right myself, but it's simple enough here that the library overhead isn't worth it, and it's more defensible in an interview. |
| `tenacity` | Battle-tested, declarative retry decorators, but another dependency for what's a ~15-line function here. |
| **Chunk during ingestion** (chosen) | Ingestion re-runs are heavier (chunking work happens every ingest, not deferred), but keeps Phase 3 a clean "index what's already chunked" step and keeps chunk boundaries stable/citable. |
| Chunk during search/indexing | Keeps ingestion lighter, but couples chunk boundaries to whichever indexing run last touched the paper — less stable for citations. |
| **Skip-by-arxiv-id idempotency** (chosen) | Won't catch silent upstream content edits to an unchanged ID (rare on arXiv), but avoids re-downloading/re-parsing PDFs on every run. |
| Full re-ingest every run | Simple and always fresh, but wasteful and hammers arXiv's servers/rate limits for no reason on repeat runs. |
| Content-hash change detection | Most correct, but arXiv already versions changed papers via ID suffix, so the added complexity buys little. |

## 6. Common failure stories & fixes

### Real failures encountered during implementation

**arXiv API redirects `http://` to `https://`, and `httpx.get` doesn't
follow redirects by default.** The live smoke test failed immediately with
`httpx.HTTPStatusError: Redirect response '301 Moved Permanently'`. arXiv
now requires HTTPS for `export.arxiv.org`, but `settings.arxiv_api_base_url`
defaulted to `http://`, and the retry decorator dutifully retried the same
failing request three times before giving up (since `raise_for_status()`
treats an unfollowed redirect response as an HTTP error). Fixed two ways:
changed the default base URL to `https://export.arxiv.org/api/query`, and
added `follow_redirects=True` to the `httpx.get()` call as defense in depth
in case arXiv redirects again in the future (e.g. to a versioned API path).
This was only caught because the spec's task list included a live smoke
test against the real API — none of the mocked unit tests (which construct
their own fake 200 response) would ever have surfaced it.

**`make lint` passed but `pre-commit run --all-files` failed on the same
code.** After all new code was written and `make lint` (which runs mypy
inside the project's own `uv`-managed venv, with every real dependency
installed) passed clean, `pre-commit run --all-files` still failed mypy
with `Returning Any from function declared to return "str"` and `Untyped
decorator makes function ... untyped`. The pre-commit `mypy` hook runs in
its *own* isolated environment, populated only from
`.pre-commit-config.yaml`'s `additional_dependencies` list — which still
only had `pydantic`, `pydantic-settings`, `fastapi` from Phase 1. Without
`httpx`, `pdfplumber`, or `pytest` installed in that isolated environment,
mypy couldn't see their type stubs and silently treated everything touching
them as `Any` (for `httpx.get(...).text`) or "untyped" (for
`@pytest.fixture`-decorated test functions). Fixed by adding `httpx`,
`pdfplumber`, and `pytest` to the hook's `additional_dependencies`. Lesson:
`make lint` and the pre-commit hook are two *separate* mypy environments
that can silently drift — every new runtime or test dependency added to
`pyproject.toml` also needs to be added to
`.pre-commit-config.yaml`'s mypy `additional_dependencies`, or pre-commit's
type checking quietly gets weaker instead of erroring loudly.

### Anticipated failure modes (not yet encountered)
Requested ahead of implementation as reference material. These are
**plausible failure modes based on how the pieces work, not things that
have actually happened** — do not cite these as real incidents in an
interview. Any that do occur during the build get promoted to the "Real
failures" section above with what actually happened.

- **arXiv rate-limiting / 429s on burst requests.** arXiv asks for
  reasonable request spacing; a tight loop over many PDF downloads without
  delay could get throttled or blocked. Mitigation already designed in:
  a configurable delay between requests plus exponential backoff on
  failure.
- **Malformed or unparseable PDF text.** Some arXiv PDFs are scans, have
  broken encoding, or are LaTeX-generated with unusual ligatures/columns
  that `pdfplumber` extracts as garbled text (e.g., multi-column papers
  interleaving column text). Mitigation: log and skip papers where
  extracted text is suspiciously short relative to page count, rather than
  storing garbage chunks silently.
- **Partial ingestion on crash mid-run.** If the process dies after
  inserting a paper's metadata row but before its chunks are written (or
  mid-PDF-download), a re-run's "skip if arxiv_id exists" idempotency check
  could skip a paper that's actually incomplete. Mitigation: only mark a
  paper as fully ingested (e.g., an `ingested_at` timestamp set) after
  chunks are successfully stored; skip logic checks that flag, not just
  row existence.
- **Duplicate/near-duplicate chunks from re-ingesting an updated paper
  version.** If `--force` re-ingests an arXiv ID whose PDF changed without
  a version bump, old chunks could remain alongside new ones. Mitigation:
  `--force` deletes existing chunks for that arxiv_id before inserting new
  ones (replace, not append).
- **SQLite "database is locked" under concurrent access.** SQLite allows
  only one writer at a time; if ingestion runs while the FastAPI app also
  has an open write connection, one could block or error. Mitigation: keep
  connections short-lived (open/close per operation, not held open) and
  set a busy_timeout so concurrent access retries briefly instead of
  failing immediately.
- **Disk space from accumulating PDFs.** Downloading PDFs for a large
  query (e.g., thousands of results) could fill local disk. Mitigation:
  `max_results` is required and defaults small; PDFs are gitignored and
  documented as a local cache, not part of the repo.

## Tasks
- [x] Add `httpx` and `pdfplumber` to `pyproject.toml`; `uv sync`.
- [x] Extend `src/config.py`: arXiv API base URL, default max results,
      request delay, SQLite DB path, PDF storage directory.
- [x] `src/db/schema.py` — `papers` and `chunks` table DDL + `init_db()`.
- [x] `src/db/connection.py` — SQLite connection helper (short-lived
      connections, `busy_timeout`, foreign keys on).
- [x] `src/db/repository.py` — `PaperRepository` (upsert, get-by-id,
      list, mark-ingested) and `ChunkRepository` (replace-chunks-for-paper,
      get-by-paper) — no inline SQL outside this module.
- [x] `src/models/paper.py` — Pydantic models: `Paper`, `Chunk`.
- [x] `src/services/arxiv_client.py` — search arXiv, parse Atom XML,
      retry/backoff wrapper.
- [x] `src/services/pdf_parser.py` — download PDF, extract text via
      `pdfplumber`.
- [x] `src/services/chunker.py` — paragraph-aware fixed-window chunker
      with overlap.
- [x] `src/services/ingestion.py` — orchestration: query → per-paper
      upsert/download/parse/chunk/store, idempotent skip, `--force`
      replace.
- [x] `src/ingest.py` — CLI entrypoint (argparse: query, max-results,
      force), runnable via `uv run python -m src.ingest`.
- [x] Tests: `arxiv_client` (mocked HTTP), `chunker` (deterministic),
      `repository` (temp SQLite file), `ingestion` orchestration (mocked
      client/parser).
- [x] `.gitignore`: add `data/` (PDF storage + SQLite DB working directory).
- [x] Live smoke test against the real arXiv API for a small query,
      inspect resulting SQLite rows, then `make lint && make test`.

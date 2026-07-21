# Phase 6: Streamlit Frontend (chat + upload/status)

## 1. What's this?
A thin Streamlit UI over the FastAPI backend, plus the small set of new
backend endpoints the UI needs that didn't exist yet:

- **New backend endpoints** (`src/routers/papers.py`): `POST /ingest`
  (triggers arXiv ingestion for a query), `POST /reindex` (rebuilds the
  BM25/Qdrant search indices from current SQLite state), `GET /papers`
  (lists ingested papers + chunk counts). Until now, ingestion and
  indexing were CLI-only (`src/ingest.py`, `src/index.py`) — a UI that's
  "thin client only, calls FastAPI, no business logic" per CLAUDE.md needs
  these operations reachable over HTTP.
- **`streamlit_app/Home.py`**: landing page with a live backend health
  check.
- **`streamlit_app/pages/1_Chat.py`**: multi-turn chat over `POST /chat`,
  with each answer's reasoning trace shown inline via `st.expander` —
  never a separate page.
- **`streamlit_app/pages/2_Upload_Status.py`**: a form to trigger
  ingestion by arXiv query, a button to rebuild search indices, and a
  table of currently-ingested papers.
- **`streamlit_app/api_client.py`**: the only place the frontend talks to
  the backend — every page calls through this module, never `src.*`
  directly.

## 2. Why this?
This is the first user-facing surface in the whole project — everything
through Phase 5 was only reachable via `curl`/CLI. It's also the phase
that forces the "thin client, no business logic" boundary from CLAUDE.md
to become real: the frontend literally cannot share code with the
backend (different top-level package, excluded from the backend's mypy
config), so every capability the UI needs has to already exist as an HTTP
endpoint — which is what surfaces that ingestion and indexing were never
exposed over HTTP.

## 3. Options I had
**Page structure:** Streamlit's native `pages/` directory (auto-discovered
sidebar navigation) vs. a single page with `st.tabs()` vs. a sidebar
`st.radio` mode-selector.

**Trace display:** `st.expander` inline under each chat message vs. a
separate "trace" page/tab vs. a sidebar panel.

**"Upload" semantics:** true file upload (`st.file_uploader` for PDFs) vs.
arXiv-query-triggered ingestion (matching the existing arXiv-API-only
ingestion pipeline from Phase 2).

**Ingestion/reindex triggering:** synchronous (blocking) HTTP call with a
UI spinner vs. background task + polling for completion.

**Frontend-to-backend coupling:** a shared `api_client.py` module used by
every page vs. inline `httpx`/`requests` calls scattered per page.

**Frontend config:** import `src.config.settings` directly vs. the
frontend reading its own `API_BASE_URL` env var independently.

## 4. Why I chose what I chose
- **Native `pages/` directory**: CLAUDE.md's own wording is "chat page...
  + upload/status page" — two distinct pages, not two modes of one page.
  Streamlit's built-in multi-page convention is the standard way to get
  that with sidebar navigation for free, no custom routing code needed.
- **`st.expander` inline, not a separate page**: this is explicit in
  CLAUDE.md's deliberate-changes table — "trace shown inline rather than
  as a separate page to reduce build time." An expander directly under
  each chat message keeps the trace one click away without leaving the
  conversation.
- **arXiv-query-triggered ingestion, not file upload**: the backend's
  entire ingestion pipeline (Phase 2) is arXiv-API-driven — there is no
  PDF-upload code path, and building one (validation, storage, parsing an
  arbitrary uploaded file) would be new backend work out of scope for a
  frontend phase. "Upload" here means "add papers to the corpus," which
  the existing pipeline already does by arXiv query — a deliberate
  reinterpretation worth being able to explain, not an oversight.
- **Synchronous ingestion/reindex calls**: every other endpoint in this
  project is synchronous; adding a background job queue for exactly two
  admin-style actions would be new infrastructure (contradicting the
  "keep infra minimal" theme) for an operation a single user triggers
  occasionally. The UI shows a spinner and accepts the wait — the known
  trade-off is a blocked FastAPI worker for the duration, acceptable at
  this project's single-user scale and stated explicitly as a limitation.
- **Shared `api_client.py`**: keeps every page genuinely thin (parse
  input, call one function, render output) and gives one place to change
  the base URL, timeout, or error handling — consistent with the project's
  existing pattern of thin routers calling into a service layer, just
  applied to the frontend's HTTP boundary instead of the backend's DB
  boundary.
- **Frontend reads its own `API_BASE_URL` env var, doesn't import
  `src.config`**: the whole point of "thin client, no business logic" is
  that the frontend could be deployed as a genuinely separate process
  (different container, different host) from the backend. Importing
  `src.config.settings` would silently couple the two — the frontend
  should only ever know "the backend lives at this URL," nothing about
  Qdrant hosts, LLM providers, or anything else the backend config knows.

## 5. Possible approaches & trade-offs
| Approach | Trade-off |
|---|---|
| **Native `pages/` multi-page app** (chosen) | Streamlit's file-based routing is opinionated (numeric prefixes control ordering), but needs zero custom navigation code and matches CLAUDE.md's "two pages" wording directly. |
| `st.tabs()` single page | More control over layout within one page, but doesn't match "chat page + upload/status page" as CLAUDE.md states it, and mixes an admin/status UI into the same page as the conversational one. |
| **`st.expander` inline trace** (chosen) | Trace is collapsed by default (one extra click to see it), but keeps it attached to the message it explains rather than a disconnected page you have to cross-reference. |
| Separate trace page | Full detail always visible if wanted, but exactly the "separate page" CLAUDE.md's own reasoning explicitly rejected — loses the "trace next to the answer it explains" property. |
| **arXiv-query ingestion, not file upload** (chosen) | Doesn't support "I have a PDF on my laptop, ingest this exact file" — only arXiv-indexed papers. Matches the existing pipeline exactly, no new backend surface needed. |
| Real file upload | More literal match to "upload," but requires new backend PDF-handling code (storage, validation, parsing an arbitrary file vs. a known arXiv PDF URL) that doesn't exist and is out of this phase's scope. |
| **Synchronous ingest/reindex** (chosen) | Blocks the UI (and a FastAPI worker) for the duration of ingestion/embedding — could be tens of seconds to minutes for a larger query. Simple, no new infra. |
| Background task + polling | Non-blocking UI, but needs a task queue or at minimum an in-process background-task mechanism plus a status-polling endpoint — meaningfully more infrastructure for two admin actions. |
| **Shared `api_client.py`** (chosen) | One more file/module to maintain, but keeps every page thin and centralizes base-URL/error handling in one place. |
| Inline HTTP calls per page | Marginally less code up front, but duplicates request/error-handling logic across pages and makes a base-URL change a multi-file edit. |
| **Frontend owns its own `API_BASE_URL`** (chosen) | One more env var to configure, but the frontend has zero coupling to backend internals — genuinely deployable as a separate process. |
| Import `src.config.settings` | Less config duplication, but breaks the "thin client, no business logic" boundary — the frontend would depend on backend-internal config it has no business knowing about. |

## 6. Common failure stories & fixes

### Real failures encountered during implementation
_(left empty until we actually hit and solve real problems — filled in after the build, not invented)_

### Anticipated failure modes (not yet encountered)
Reference material only — **plausible failure modes based on how the
pieces work, not things that have actually happened.** Do not cite these
as real incidents in an interview. Any that do occur get promoted to the
"Real failures" section above with what actually happened.

- **Ingestion/reindex request timing out on a large query.** A synchronous
  HTTP call blocking on tens of PDF downloads + embeddings could exceed a
  default HTTP client timeout (Streamlit's requests, a reverse proxy, or
  the browser itself), leaving the UI in an ambiguous "did it work?"
  state even if the backend eventually finishes. Mitigation: keep the
  documented/recommended `max_results` small for interactive use via the
  UI; the CLI remains the right tool for large bulk ingestion runs.
- **Chat session state growing unbounded in a long session.** Streamlit's
  `st.session_state` chat history has no eviction — an extremely long
  session could accumulate a large in-memory list client-side. Acceptable
  at single-user portfolio scale; a real multi-user deployment would need
  a cap or server-side session storage.
- **Rate limiting surfacing as a confusing raw 429 in the UI.** If a user
  (or a double-clicked button) trips `/chat` or `/search`'s rate limit,
  the raw HTTP 429 needs to be caught and shown as a friendly "slow down"
  message rather than an unhandled exception in the Streamlit page.
- **Backend unreachable entirely** (Compose stack not running). Every page
  should degrade to a clear "backend unreachable" message rather than a
  raw connection-error traceback — this is why `api_client.py` centralizes
  error handling instead of leaving each page to catch `httpx` exceptions
  independently.

## Tasks
- [x] Add `streamlit` to `pyproject.toml`; `uv sync`.
- [x] Extend `src/config.py`: `rate_limit_ingest`.
- [x] `src/models/papers.py` — Pydantic `IngestRequest`, `IngestResponse`,
      `ReindexResponse`, `PaperSummary`.
- [x] `src/routers/papers.py` — `POST /ingest`, `POST /reindex`,
      `GET /papers`, rate-limited.
- [x] Wire `papers.router` into `src/main.py`.
- [x] `streamlit_app/api_client.py` — thin HTTP wrapper: `get_health`,
      `post_chat`, `post_ingest`, `post_reindex`, `get_papers`; centralized
      error handling for unreachable backend / non-2xx responses.
- [x] `streamlit_app/Home.py` — landing page + live health check.
- [x] `streamlit_app/pages/1_Chat.py` — multi-turn chat, inline expandable
      trace per message.
- [x] `streamlit_app/pages/2_Upload_Status.py` — ingest form, reindex
      button, papers table.
- [x] Tests: new `/ingest`, `/reindex`, `/papers` endpoints (mocked
      services); Streamlit pages via `AppTest` (mocked `api_client`) for
      the chat happy/rejected paths and the upload/status page.
- [x] Live verification: full Compose stack up, run
      `uv run streamlit run streamlit_app/Home.py`, use the browser to
      ingest a real paper via the UI, rebuild indices via the UI, chat
      about it and expand the trace, then `make lint && make test`.

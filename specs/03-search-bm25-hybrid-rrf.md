# Phase 3: Search — BM25 + Hybrid RRF

## 1. What's this?
Turns the chunks stored in SQLite (Phase 2) into a searchable corpus, via
two retrieval methods built and compared together:
- **BM25 keyword search** (`src/services/bm25_index.py`): `rank_bm25`
  index over all chunk text, persisted to disk.
- **Vector search** (`src/services/vector_index.py` +
  `src/services/embeddings.py`): chunk embeddings (`sentence-transformers`)
  upserted into Qdrant; query-time nearest-neighbor search.
- **Hybrid fusion** (`src/services/rrf.py`): Reciprocal Rank Fusion
  combining BM25 and vector ranked lists into one ranking.
- **Comparison tool** (`src/search_cli.py`): given a query, prints BM25-only,
  vector-only, and hybrid results side by side.
- **Index build script** (`src/index.py`): reads chunks from SQLite, builds
  both indices.
- **`GET /search` endpoint** (`src/routers/search.py`): exposes hybrid
  search (with a `mode` query param for bm25/vector/hybrid) over the app.

Out of scope: anything agentic (Phase 4 consumes this search layer via
LangGraph nodes, doesn't build it).

## 2. Why this?
This is the retrieval backbone every later phase depends on: Phase 4's
`retrieve` node calls into this search layer, and Phase 7's evaluation
harness measures retrieval precision/recall against it. Building BM25 and
vector search together (rather than as sequential phases) means the
hybrid-vs-single-method comparison — the actual interview-relevant
question ("why hybrid, and does it help?") — gets answered with real
numbers from day one, instead of retrofitted later.

## 3. Options I had
**Embedding model:** `sentence-transformers` (local, e.g. all-MiniLM-L6-v2)
vs. Jina AI embeddings API vs. OpenAI/Claude embeddings API.

**Fusion strategy:** Reciprocal Rank Fusion (rank-based) vs. weighted score
normalization (e.g., min-max normalize BM25 and cosine scores, then
weighted sum) vs. a learned re-ranker (cross-encoder).

**BM25 index persistence:** pickle the built index to disk vs. rebuild
in-memory on every process start vs. store tokenized corpus in SQLite and
rebuild lazily.

**Where indices are built:** a separate `src/index.py` script (mirroring
`src/ingest.py`) vs. building indices automatically inside the ingestion
pipeline vs. building lazily on first search request.

**Candidate pool size before fusion:** fixed top-N per method (e.g. top 20)
vs. fusing over each method's entire ranked corpus.

## 4. Why I chose what I chose
- **`sentence-transformers`**: runs fully offline after the one-time model
  download — no API key, no per-embedding cost, deterministic output
  (same input always produces the same vector, useful for reproducible
  eval later). Jina/OpenAI embeddings would add network dependency and
  cost to something that runs on every ingested chunk and every query.
- **Reciprocal Rank Fusion**: rank-based fusion sidesteps the score-scale
  problem entirely — BM25 scores and cosine similarities live on
  incomparable scales, so combining them by weighted sum requires
  ad hoc normalization tuning. RRF only cares about *rank position* in
  each list, which is simpler to reason about and defend ("a document
  ranked #1 by both methods should win, regardless of what its raw scores
  were") and is what the reference project and CLAUDE.md specify.
- **Persisted BM25 index (pickle)**: rebuilding `rank_bm25`'s index from
  scratch on every FastAPI process start means re-tokenizing the entire
  corpus before the app can serve a single search request. Persisting to
  disk after `src/index.py` runs makes startup just a deserialize.
- **Separate `src/index.py` script**: keeps "ingest new papers" and
  "(re)build search indices" as independently runnable steps — you can
  add papers without immediately paying embedding/indexing cost, and you
  can rebuild indices (e.g., after changing chunk size) without
  re-ingesting. Mirrors the existing `src/ingest.py` pattern.
- **Fixed candidate pool (top 20) per method before fusion**: fusing over
  the entire corpus ranking is wasted work — RRF's `1/(k+rank)` weight
  decays fast, so results ranked below ~20-30 in either list essentially
  never affect the fused top-5. Capping the pool keeps both BM25 and
  Qdrant queries cheap.

## 5. Possible approaches & trade-offs
| Approach | Trade-off |
|---|---|
| **`sentence-transformers`** (chosen) | Adds a `torch`-sized dependency and a one-time model download, but zero marginal cost per embed and fully reproducible/offline. |
| Jina AI embeddings API | No heavy local dependency, but adds network latency, an API key requirement, and per-call cost to both indexing and every query. |
| OpenAI/Claude embeddings | Same network/cost trade-off as Jina, plus ties the embedding model to the same vendor as the LLM — less flexibility to swap independently. |
| **Reciprocal Rank Fusion** (chosen) | Ignores *how much* better a top result was (rank 1 vs. rank 2 by a landslide look the same), but avoids fragile score normalization across incomparable scales. |
| Weighted score normalization | Can encode "how much better," but min-max normalization is sensitive to outliers and the BM25/cosine weight ratio becomes another hyperparameter to tune and justify. |
| Cross-encoder re-ranker | Best result quality (reads query+doc together), but adds a second model, extra latency per query, and is arguably its own phase's worth of complexity — deferred as a "next step" talking point, not built here. |
| **Persisted BM25 index** (chosen) | Index must be explicitly rebuilt after re-ingestion (`src/index.py` rerun) — a manual step to remember — but avoids re-tokenizing the whole corpus on every app restart. |
| Rebuild BM25 in-memory at startup | Always fresh, zero staleness risk, but every FastAPI restart re-tokenizes the full corpus — fine at small scale, but a real cost that would compound at larger scale. |
| **Separate index-build script** (chosen) | One more script/command to remember to run, but decouples "add data" from "pay indexing cost," and matches the existing ingestion-script pattern. |
| Auto-index during ingestion | One command does everything, but couples ingestion speed to embedding speed, and re-running search-index changes (e.g. new chunk size) would force a full re-ingest to get new indices. |
| **Fixed candidate pool (top 20/method)** (chosen) | Could in theory miss a document that ranks, say, 25th in BM25 but would climb into the fused top-5 given more candidates — vanishingly rare in practice given RRF's fast rank decay. | Fuse full corpus rankings | Never misses a fusion candidate, but forces both BM25 and Qdrant to rank/return the entire corpus on every query — wasted work at any real scale. |

## 6. Common failure stories & fixes

### Real failures encountered during implementation

**BM25 IDF becomes exactly zero on tiny/degenerate corpora, silently
hiding a genuinely relevant result.** A unit test seeded a 2-document
corpus where the query term appeared in exactly 1 of the 2 documents. The
BM25Okapi IDF formula, `log((N - n + 0.5) / (n + 0.5))`, evaluates to
`log((2-1+0.5)/(1+0.5)) = log(1) = 0` in that exact case — not a bug in
`rank_bm25`, just what the formula does at `N = 2n`. Since our
`Bm25Index.search()` filters out zero-score results (`score > 0`, to avoid
returning irrelevant matches), the one genuinely relevant document got
silently dropped, and the test failed with an empty results list instead
of the expected top hit. Fixed by adding a third, unrelated document to
the test fixture, moving the corpus out of the exact `N = 2n` degenerate
case — real corpora essentially never hit this coincidence, but it's a
concrete illustration of a documented, known limitation of this project:
`rank_bm25` on a small in-memory corpus behaves differently at the edges
than a hosted search engine would at production scale.

**`make lint` passed but `pre-commit run --all-files` timed out entirely**
(3+ minutes, no completion) after adding `qdrant-client`,
`sentence-transformers`, and `rank-bm25` to the mypy hook's
`additional_dependencies` — the same fix that worked in Phase 2 for
lightweight packages. The pre-commit `mirrors-mypy` hook builds its own
fully isolated virtualenv from that dependency list, completely separate
from the project's `uv`-managed venv; asking it to install
`sentence-transformers` meant re-downloading and installing `torch` and
the rest of its dependency tree a second time, in a different environment,
on every environment rebuild. This is strictly worse than Phase 2's
version of this problem (missing stubs) — it doesn't just weaken type
checking, it makes the hook impractically slow. Fixed by replacing the
`mirrors-mypy` repo hook with a `local`/`language: system` hook that runs
`uv run mypy src` directly against the project's own already-synced venv —
the same command `make lint` already runs, so there is now exactly one
mypy environment for the whole project, not two. Lesson: for a `uv`-managed
project, mirroring dependencies into a second pre-commit-managed
environment doesn't scale past a couple of lightweight packages — running
the tool through the project's own environment is both simpler and
strictly more correct (it's checking against the exact same installed
versions `make lint` and CI would use).

### Anticipated failure modes (not yet encountered)
Reference material only — **plausible failure modes based on how the
pieces work, not things that have actually happened.** Do not cite these
as real incidents in an interview. Any that do occur get promoted to the
"Real failures" section above with what actually happened.

- **BM25 index and Qdrant collection drifting out of sync with SQLite.**
  If papers are ingested (Phase 2) but `src/index.py` isn't re-run, or is
  re-run only partially, search results reflect a stale corpus — chunks
  exist in SQLite but aren't searchable, or (worse) deleted/changed chunks
  are still searchable. Mitigation: `src/index.py` always does a full
  rebuild from the current SQLite state (not an incremental update),
  so there's exactly one source of truth and no drift accumulates across
  runs — the trade-off is rebuild cost scales with total corpus size, not
  just what changed.
- **Embedding model first-run download failing or being slow in a
  restricted/offline environment.** `sentence-transformers` downloads
  model weights from Hugging Face Hub on first use; a firewalled CI
  environment or Docker build without network access would fail here.
  Mitigation: document the one-time download requirement clearly, and
  consider baking the model into the Docker image in a later phase if this
  becomes a real deployment blocker.
- **Qdrant collection created with the wrong vector dimension** if the
  embedding model is ever swapped (e.g., a different sentence-transformers
  checkpoint with a different output dimension) without recreating the
  collection — Qdrant would reject upserts with a dimension mismatch
  error. Mitigation: `src/index.py`'s collection setup checks the existing
  collection's configured dimension against the current model's dimension
  and fails loudly (rather than silently corrupting) on mismatch.
- **RRF fusion producing a confusing "why did this rank here" result** for
  users/interviewers — a document that's rank 1 in BM25 but absent from
  the vector top-20 (or vice versa) still gets folded into a single fused
  score with no visibility into which method contributed what. Mitigation:
  the comparison CLI (`src/search_cli.py`) always shows each method's
  results separately alongside the fused ranking, specifically so this
  is inspectable rather than hidden.
- **Chunk text truncated mid-sentence in search results** because chunk
  boundaries were chosen for indexing size (Phase 2's chunker), not
  reading quality — a returned top result might start or end mid-word.
  Mitigation: acceptable for this phase (chunk boundaries are a known,
  documented trade-off from Phase 2); a future improvement would be
  returning a small window of surrounding text for display purposes.

## Tasks
- [x] Add `qdrant-client`, `sentence-transformers`, `rank_bm25` to
      `pyproject.toml`; `uv sync`.
- [x] Extend `src/config.py`: Qdrant collection name, embedding model
      name/dimension, BM25 index path, RRF `k` constant, candidate pool
      size, default result count.
- [x] `src/models/search.py` — Pydantic `SearchResult`, `SearchResponse`.
- [x] `ChunkRepository.get_by_id` / `PaperRepository.get_by_id` additions
      needed for result hydration.
- [x] `src/services/embeddings.py` — `EmbeddingModel` wrapper
      (embed texts, embed single query).
- [x] `src/services/bm25_index.py` — build from chunk rows, persist/load
      via pickle, `search(query, top_k)`.
- [x] `src/services/vector_index.py` — Qdrant collection setup, upsert,
      `search(query_vector, top_k)`.
- [x] `src/services/rrf.py` — `reciprocal_rank_fusion(rankings, k)`.
- [x] `src/services/search.py` — orchestration: `bm25_search`,
      `vector_search`, `hybrid_search`, all returning hydrated
      `SearchResult`s.
- [x] `src/index.py` — CLI: rebuild BM25 index + Qdrant collection from
      current SQLite state.
- [x] `src/search_cli.py` — CLI: run a query through all three modes,
      print a side-by-side comparison table.
- [x] `src/routers/search.py` — `GET /search?q=...&mode=...&top_k=...`.
- [x] Tests: `rrf` (deterministic fusion math), `bm25_index` (tiny fixed
      corpus), `search` orchestration (mocked embedding model + in-memory
      Qdrant client), `/search` endpoint (mocked search service).
- [x] Live verification: start the full Compose stack, run `src/index.py`
      against the Phase 2 ingested papers, run `src/search_cli.py` with a
      real query, hit `GET /search` over HTTP, then `make lint && make test`.

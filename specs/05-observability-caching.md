# Phase 5: Observability + Caching (Langfuse + Redis + slowapi)

## 1. What's this?
Three production-signal pieces layered onto the working agentic pipeline:
- **Langfuse tracing** (`src/services/tracing.py`): every pipeline call —
  each LangGraph node, both search functions, and every LLM call — is
  wrapped in a Langfuse trace/span, giving a hierarchical view of what a
  single query actually did (which nodes ran, how many rewrites, what each
  LLM call cost).
- **Redis response caching** (`src/services/cache.py`): identical repeated
  queries to `/search` and `/chat` are served from cache instead of
  re-running retrieval/generation.
- **slowapi rate limiting**: `/search` and `/chat` get per-IP request
  limits, using the already-running Redis instance as shared limiter
  storage instead of in-memory (in-memory limits reset per worker process
  and don't work correctly with multiple app instances).

## 2. Why this?
CLAUDE.md calls Langfuse and Redis out explicitly as "our strongest
production-signal components... not being simplified further" — this is
the phase that makes that claim true instead of aspirational. Tracing
turns "the agent did something" into "here's exactly what it did, in what
order, at what cost" — the difference between a demo and something you can
debug and optimize. Caching and rate limiting are the two most basic
production concerns for an LLM-backed endpoint: repeated identical queries
shouldn't re-pay LLM cost, and public endpoints shouldn't be able to run
up an unbounded API bill.

## 3. Options I had
**Langfuse deployment:** Langfuse Cloud (hosted SaaS) vs. self-hosted
Langfuse as a 4th Docker Compose service vs. no Langfuse (skip this piece
of the reference project).

**Tracing granularity:** wrap every function (nodes, search, LLM calls)
vs. only wrap the top-level pipeline entrypoint vs. only wrap LLM calls
(the most expensive/interesting part).

**Cache key granularity:** cache full endpoint responses keyed by
normalized query text vs. cache only the expensive sub-steps (embeddings,
LLM completions) individually.

**Rate limit storage:** in-memory (per-process) vs. Redis-backed (shared
across processes/workers).

**Graceful degradation when Langfuse isn't configured:** hard-require
Langfuse credentials to run the app vs. no-op tracing when unconfigured.

## 4. Why I chose what I chose
- **Langfuse Cloud, not self-hosted**: CLAUDE.md's own constraint caps
  Docker Compose at 3 services (app, Qdrant, Redis) — "no Kubernetes, no
  Airflow, no OpenSearch" is explicitly about not letting infra sprawl.
  Self-hosting Langfuse would mean at least one more container (Langfuse
  itself needs its own Postgres/ClickHouse in a full self-hosted setup),
  directly violating that cap. Langfuse Cloud's free tier gives the same
  tracing UI and API without adding infra — the trade-off is an external
  SaaS dependency instead of a fully self-contained stack, which is
  explicitly worth surfacing as a deliberate call, not an oversight.
- **Wrap every layer (nodes, search, LLM calls), not just the top level**:
  a trace that only shows "chat took 4.2s" is barely more useful than a
  log line. A trace that shows guardrail → retrieve (0.3s, 5 chunks) →
  grade (0.8s, LLM call, 3/5 kept) → generate (2.1s, LLM call, cost $0.004)
  is the actual point of tracing — it's what makes a slow or expensive
  query debuggable instead of a black box.
- **Cache full responses keyed by normalized query text**: this project's
  actual latency/cost driver is LLM calls, and caching at the response
  level means a repeated identical question skips the entire pipeline
  (retrieval + up to 4 LLM calls), not just one sub-step. Caching
  individual sub-steps (e.g. just embeddings) would still re-pay for
  guardrail/grade/generate LLM calls on every repeat — most of the actual
  cost.
- **Redis-backed rate limiting**: reuses the Redis service already
  required for caching — no new infrastructure, and (unlike in-memory
  limits) correctly enforces limits if the app ever runs as more than one
  process/worker, which an in-memory counter can't do.
- **No-op tracing when Langfuse isn't configured**: Langfuse credentials
  are an external SaaS account, same category of thing as the LLM API
  keys from Phase 4. Requiring them just to run `make test` or start the
  app locally would repeat the exact friction Phase 4 hit around API
  keys — the app must run without them, with tracing silently absent
  rather than the app crashing or every test needing a Langfuse account.

## 5. Possible approaches & trade-offs
| Approach | Trade-off |
|---|---|
| **Langfuse Cloud** (chosen) | External SaaS dependency and a free-tier usage cap, but zero added infrastructure — stays within the 3-service Compose limit. |
| Self-hosted Langfuse | Fully self-contained stack, but needs at least one more container (realistically two — Langfuse plus its own datastore), breaking the explicit "max 3 services" constraint. |
| Skip Langfuse entirely | Simplest, but drops one of the two components CLAUDE.md explicitly calls out as a strongest production-signal piece — a real regression versus the reference project. |
| **Wrap every layer with tracing** (chosen) | More decorator boilerplate across the codebase, but produces traces that are actually useful for debugging/optimizing, not just "it ran." |
| Top-level-only tracing | Much less code, but a trace showing only total latency can't answer "which node was slow" or "how many rewrites happened" — most of the diagnostic value is lost. |
| **Full-response caching** (chosen) | Coarser cache granularity (a query with even a slightly different phrasing is a full cache miss), but caches the expensive part (LLM calls) end-to-end, maximizing cost savings on true repeats. |
| Sub-step caching (embeddings only) | Finer-grained reuse, but still re-pays for the guardrail/grade/generate LLM calls on every repeated query — most of the cost isn't in the embedding step. |
| **Redis-backed rate limiting** (chosen) | One more moving part in the limiter config (`storage_uri`), but correct under multiple workers/processes and reuses infrastructure already required for caching. |
| In-memory rate limiting | Zero extra config, but resets on every process restart and is wrong (each worker gets its own independent limit) the moment the app runs as more than one process. |
| **No-op tracing when unconfigured** (chosen) | Silent absence of tracing could mask a real misconfiguration in production, but keeps local dev/tests/CI free of an external account requirement — the same trade-off already made for LLM keys. |
| Hard-require Langfuse credentials | Forces every environment to have a real Langfuse account, including CI and anyone just trying to run the tests — too heavy a requirement for a portfolio project. |

## 6. Common failure stories & fixes

### Real failures encountered during implementation

**A stray, unrelated Redis server running on the host (outside Docker)
silently broke test isolation via the cache.** `test_search_router.py::
test_search_returns_503_when_index_missing` started failing after caching
was wired in — it expected a 503 but got a cached 200 from an earlier
test's response. `docker ps` showed no Redis container running yet the
test connected successfully; `redis-cli -h localhost -p 6379 ping`
returned `PONG` from something already listening on that port before our
Compose stack was even started (most likely a native/Homebrew Redis
service on this Mac, coexisting with Docker Desktop's own port-forwarding
without conflict). Two tests using the same query text shared a cache
entry across test boundaries, so a later test's expected failure path was
silently short-circuited by an earlier test's successful cached response.
Fixed with an autouse `conftest.py` fixture that replaces
`src.services.cache._client` with a mock that always raises
`redis.RedisError`, forcing every test through the cache's own
error-degrades-to-miss path deterministically — regardless of what Redis
happens to be reachable on whatever machine runs the tests. Lesson: caching
introduces implicit cross-request state; once it exists, tests can no
longer assume a clean slate just because they don't explicitly touch the
cache.

**Traces weren't nested — every `@observe`-decorated function became its
own top-level trace instead of a child span.** After wiring `@observe()`
onto every node/search/LLM function, the first live run (real Langfuse
Cloud credentials, `src/agent_cli.py`) produced *three separate top-level
traces* — `guardrail_node`, `retrieve_node`, `grade_node` — instead of one
trace showing the whole query's path. The cause: nothing wrapped the
actual entrypoint (`graph.invoke(...)`, called directly in both
`agent_cli.py` and the `/chat` router) in an `@observe()` context, so each
node's decorator had no ambient parent span to attach to and started a
fresh trace instead. Fixed by adding a `run_graph()` helper in
`src/agents/graph.py`, decorated with `@observe(name="agentic_rag_pipeline")`,
that both call sites now use instead of calling `graph.invoke()` directly
— confirmed via the Langfuse API afterward that every node/search/LLM
observation in a real run now carries a non-null `parent_observation_id`
rooted at one `agentic_rag_pipeline` trace. The original "wrap every
layer" design (section 4) was necessary but not sufficient — nesting also
requires wrapping the *entrypoint* that ties the layers together, which
was missing from the initial task list.

**Running the test suite sent real trace data to Langfuse Cloud.** Once
real Langfuse credentials were in `.env` for the live-verification step,
`uv run pytest` itself started polluting the production Langfuse project
with test traces — confirmed by querying the Langfuse API for the most
recent trace timestamp before and after a full `pytest` run and seeing it
advance, with trace names (`bm25_search`, `anthropic_complete`,
`agentic_rag_pipeline`, etc.) that only test code paths could have
produced. `test_llm.py` calls the real, `@observe`-decorated
`AnthropicLLMClient.complete` (only the underlying SDK client is mocked);
`test_search.py` calls the real `bm25_search`/`vector_search`/
`hybrid_search`; `test_chat_router.py` calls the real `run_graph` with
only `graph.invoke` mocked inside it — none of these paths were exempt
from tracing just because they were tests. Fixed by setting
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` to empty strings at the very
top of `conftest.py`, before any `src.*` import — `load_dotenv()` (called
at `src/config.py` import time) does not override an already-set
environment variable, so this forces `Settings()` to see empty Langfuse
credentials during the entire test session regardless of what's actually
in `.env`, which keeps `tracing_enabled=False` for every test run.
Verified by the same before/after trace-timestamp check showing no
movement across a full test run afterward. Lesson: a credential added to
`.env` for one specific live-verification step silently applies to *every*
process that imports the config, including the test suite — "it's in
`.env`" is not the same as "it's scoped to where I meant it."

### Anticipated failure modes (not yet encountered)
Reference material only — **plausible failure modes based on how the
pieces work, not things that have actually happened.** Do not cite these
as real incidents in an interview. Any that do occur get promoted to the
"Real failures" section above with what actually happened.

- **Cache staleness after re-indexing.** If `src/index.py` is re-run
  (new papers, changed chunking), a cached `/search` or `/chat` response
  for a query asked before and after re-indexing would return the old,
  now-stale answer for the remainder of the TTL. Mitigation: TTL is
  intentionally short (not infinite) so staleness self-heals within an
  hour, rather than requiring an explicit cache-invalidation step tied to
  the indexing pipeline.
- **Langfuse background flush losing traces on process exit.** The
  Langfuse SDK batches spans and sends them asynchronously; a short-lived
  process (like `agent_cli.py`) that exits immediately after the graph
  call could exit before the batch flushes, silently losing the trace.
  Mitigation: an explicit `flush_traces()` call at the end of
  `agent_cli.py`'s `main()`, and a FastAPI shutdown event handler for the
  long-running app process.
- **Redis outage degrading availability, not just performance.** If
  caching and rate limiting both hit Redis synchronously on every request
  with no fallback, a Redis outage would take `/search` and `/chat` down
  entirely rather than just losing caching/limiting. Mitigation: cache
  reads/writes are wrapped so a Redis error is treated as a cache miss
  (degrades to "always recompute," not "always 500"); rate limiting is a
  separate, harder call — `slowapi`'s `in_memory_fallback` option exists
  for exactly this, worth revisiting if this becomes a real production
  concern.
- **Rate limit keyed by IP behind a shared NAT/proxy.** `get_remote_address`
  keys limits by client IP; multiple users behind the same corporate NAT
  or proxy would share one rate-limit bucket. Acceptable for a
  single-user portfolio project's actual traffic pattern, but a known
  limitation if this were ever exposed more broadly.

## Tasks
- [x] Add `langfuse`, `redis`, `slowapi` to `pyproject.toml`; `uv sync`.
- [x] Extend `src/config.py`: `langfuse_public_key`, `langfuse_secret_key`,
      `langfuse_host`, `redis_cache_ttl_seconds`, `rate_limit_search`,
      `rate_limit_chat`.
- [x] `src/services/tracing.py` — explicit `Langfuse` client construction
      from `Settings` (not implicit env-var detection — the Phase 4
      lesson), `observe` re-export, `flush_traces()`.
- [x] `src/services/cache.py` — Redis client wrapper: `get_cached`,
      `set_cached`, both tolerant of Redis errors (log + treat as miss),
      plus a stable cache-key builder.
- [x] Decorate agent nodes (`guardrail`, `retrieve`, `grade`, `rewrite`,
      `generate`), `LLMClient.complete` implementations
      (`as_type="generation"`), and `bm25_search`/`vector_search`/
      `hybrid_search` with `@observe(...)`.
- [x] Wire Redis caching into `GET /search` and `POST /chat`.
- [x] Wire slowapi `Limiter` into `src/main.py` (Redis-backed
      `storage_uri`, exception handler), apply per-route limits to
      `/search` and `/chat`.
- [x] `flush_traces()` call at the end of `src/agent_cli.py` and on
      FastAPI shutdown.
- [x] Tests: cache (mocked Redis — hit, miss, error-degrades-to-miss),
      rate limiting (exceeding the limit returns 429), tracing doesn't
      break existing node/search/LLM tests when unconfigured.
- [x] Live verification: full Compose stack up, real Langfuse Cloud
      credentials, run a query twice through `/chat` (confirm second is
      cache-served and faster), inspect the trace in the Langfuse UI,
      exceed the rate limit and confirm 429, then `make lint && make test`.

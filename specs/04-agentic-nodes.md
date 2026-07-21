# Phase 4: Agentic Nodes (guardrail → retrieve → grade → rewrite → generate)

## 1. What's this?
A LangGraph state machine that turns a raw user question into a cited answer,
using the search layer from Phase 3 as its retrieval tool:

- **`guardrail`** (`src/agents/guardrail.py`): classifies whether the query
  is in-scope (about arXiv papers / research) before spending any retrieval
  or generation budget on it. Off-topic queries short-circuit straight to a
  canned rejection.
- **`retrieve`** (`src/agents/retrieve.py`): runs `hybrid_search` (Phase 3)
  for the current query.
- **`grade`** (`src/agents/grade.py`): one LLM call asks "which of these
  retrieved chunks are actually relevant to the question?" and filters down
  to the relevant subset.
- **`rewrite`** (`src/agents/rewrite.py`): if too few chunks graded
  relevant, an LLM call reformulates the query and the graph loops back to
  `retrieve` — capped at a max number of rewrites.
- **`generate`** (`src/agents/generate.py`): produces the final answer from
  the graded-relevant chunks, citing paper titles/arXiv IDs.
- **`src/agents/graph.py`**: wires the above into a LangGraph `StateGraph`
  with conditional routing.
- **`src/services/llm.py`**: provider-agnostic LLM client (Claude or OpenAI,
  swappable via env var — per CLAUDE.md's tech stack).
- **`POST /chat`** (`src/routers/chat.py`) and **`src/agent_cli.py`**: two
  ways to run a query through the full graph end-to-end.

## 2. Why this?
This is the "agentic" half of "agentic RAG" — the actual differentiator
CLAUDE.md calls out versus naive single-shot RAG. Phase 3 proved retrieval
works; this phase proves the system can (a) refuse to answer things outside
its domain, (b) notice when retrieval came back weak and try again instead
of confidently answering from bad context, and (c) ground its final answer
in what was actually retrieved. Phase 7's eval harness explicitly compares
naive vs. agentic RAG — this phase is what "agentic" means in that
comparison.

## 3. Options I had
**LLM provider abstraction:** a single hardcoded provider vs. a thin
provider-agnostic interface swappable via env var (Claude / OpenAI).

**Default model:** `claude-opus-4-8` (highest capability) vs.
`claude-sonnet-5` (balanced cost/quality) vs. `claude-haiku-4-5` (cheapest).

**Grading granularity:** one LLM call per retrieved chunk vs. one batched
call grading all retrieved chunks at once.

**Rewrite loop control:** unbounded retries until enough relevant chunks
found vs. a hard cap on rewrite attempts.

**Trace/observability:** nothing until Phase 5 (Langfuse) vs. a minimal
in-state `trace: list[str]` of visited nodes now.

**Dependency injection into LangGraph nodes:** module-level singletons vs.
a `build_graph(...)` factory closing over injected indices/LLM client.

## 4. Why I chose what I chose
- **Provider-agnostic `src/services/llm.py`**: CLAUDE.md's tech stack
  explicitly requires "Claude API or OpenAI API... swappable via env var."
  A thin `Protocol` + two implementations is the smallest thing that
  satisfies that without coupling every agent node to one vendor's SDK.
- **Default model `claude-sonnet-5`, not `claude-opus-4-8`**: a single user
  query can trigger up to 4 LLM calls in this graph (guardrail, grade,
  rewrite, generate). At Opus pricing that's expensive and slow for what
  are mostly short classification/extraction calls, not deep reasoning.
  Sonnet 5 is documented as reaching near-Opus quality on agentic work at
  Sonnet cost — the right default for a multi-call-per-turn pipeline.
  Configurable via env var so a quality/cost comparison against Opus is a
  one-line change, not a code change — a good interview talking point.
- **Batched grading (one call, not N)**: grading 5 retrieved chunks
  individually is 5x the latency and cost of one call that sees all 5 at
  once and returns which are relevant. The model has strictly more context
  doing it in one pass too (it can compare candidates against each other).
- **Hard-capped rewrite loop**: an ungated "keep rewriting until enough
  relevant chunks" loop can spin forever on a query that's simply outside
  the corpus's coverage (e.g. asking about a paper that was never
  ingested). A max-rewrites cap guarantees termination — after the cap,
  the graph proceeds to `generate` with whatever it has (or an
  "insufficient context" answer), rather than looping forever.
- **Minimal `trace: list[str]` now**: Phase 5 adds real Langfuse tracing,
  but having *some* visibility into which nodes ran and why (rewrote once?
  rejected by guardrail?) is useful for debugging and demoing this phase on
  its own, and costs nothing to add — it's just appending strings to state.
- **`build_graph(...)` factory with closures**: LangGraph nodes are plain
  functions of state; they don't have a built-in DI mechanism. A factory
  function that takes the BM25/vector indices and LLM client and returns a
  compiled graph keeps the nodes testable (inject fakes) without needing a
  framework-level DI container for four small functions.

## 5. Possible approaches & trade-offs
| Approach | Trade-off |
|---|---|
| **Provider-agnostic LLM client** (chosen) | A small abstraction layer to maintain, but matches the tech stack's explicit swappability requirement and avoids vendor lock-in in the agent code. |
| Hardcode one provider | Simpler code, but doesn't satisfy "swappable via env var" and makes a future provider switch a larger diff. |
| **`claude-sonnet-5` default** (chosen) | Slightly lower ceiling on hardest reasoning tasks than Opus, but the right cost/latency profile for a pipeline making several LLM calls per user turn. |
| `claude-opus-4-8` default | Highest quality per call, but 4 calls/turn at Opus pricing is a real cost concern for a project meant to demonstrate production judgment, not just capability. |
| **Batched grading** (chosen) | One LLM call must correctly reason about multiple candidates at once (slightly harder prompt), but is far cheaper/faster than N calls and lets the model compare candidates. |
| Per-chunk grading | Simpler prompt per call, but linear cost/latency in retrieved chunk count. |
| **Capped rewrite loop** (chosen) | Might occasionally give up one rewrite too early on a genuinely answerable-with-more-effort query, but guarantees the graph terminates and bounds cost per query. |
| Unbounded rewrite loop | Could in theory find the right query eventually, but risks unbounded cost/latency on out-of-corpus questions — a real production and denial-of-wallet concern. |
| **Minimal `trace` list now** (chosen) | Not real observability (no timing, no token counts — that's Phase 5), but free to add and useful for debugging/demoing this phase in isolation. | 
| No trace until Phase 5 | Less code now, but this phase would be a black box until Langfuse lands. |

## 6. Common failure stories & fixes

### Real failures encountered during implementation

**The "unparseable grading response falls back to all-relevant" mitigation
was dead code — it never actually triggered.** The original design (see
task list / trade-off table) had `grade_node` catch `ValueError`/
`IndexError` around parsing the grading LLM's response and, on failure,
treat every retrieved chunk as relevant. A test that sent garbage prose as
the fake LLM's response (`"I'm not sure how to answer that."`) expected
that fallback to kick in — instead the test failed with `graded == []`,
not all chunks. The bug was in the premise: `_parse_relevant_indices`
extracts indices with `re.findall(r"\d+", response)`, and on text with no
digits that just returns an empty set — it never raises. `int()` on a
regex-guaranteed digit string can't raise `ValueError`, and index-bounds
filtering (`1 <= i <= num_chunks`) means `retrieved[i-1]` can't raise
`IndexError` either. The `except` clause was structurally unreachable.
Fixed by deleting the dead try/except entirely — garbage LLM output now
naturally degrades to "zero relevant chunks selected," which is actually
*safer* than the originally-designed "treat everything as relevant"
fallback (it can't inject irrelevant context into the final answer), and
correctly feeds into the existing rewrite-then-retry logic instead of
needing a separate failure path. Lesson: a mitigation you can't write a
test that actually exercises the failure branch for is a sign the branch
may not be reachable at all — write the test for the failure path before
trusting the mitigation exists.

**`pydantic-settings`' `env_file=".env"` never reaches `os.environ` — third-
party SDKs that read credentials directly from the environment can't see
them.** The first live run of `src/agent_cli.py` (after the user added a
real `ANTHROPIC_API_KEY` to `.env`) failed immediately with
`anthropic.TypeError: Could not resolve authentication method`, even
though the key was correctly sitting in `.env` and `settings.llm_provider`
resolved fine. The cause: `SettingsConfigDict(env_file=".env")` only
populates pydantic-settings' own declared fields on the `Settings` object
— it doesn't export anything into the actual process environment. But
`AnthropicLLMClient` (and `OpenAILLMClient`) call the zero-arg
`anthropic.Anthropic()` / `openai.OpenAI()` constructors specifically so
credentials resolve automatically from `os.environ["ANTHROPIC_API_KEY"]`
— and that variable was never actually set anywhere. Every other config
value in this project (Qdrant host, chunk size, etc.) only ever flows
through our own `Settings` object, so this gap was invisible until the
first credential that a *different* library needed to read directly.
Fixed by calling `load_dotenv()` (from `python-dotenv`, already an
indirect dependency via `pydantic-settings`) at the top of
`src/config.py`, before `Settings()` is constructed — this actually
populates `os.environ` from `.env`, so both our own settings and any
third-party SDK reading the environment directly see the same values.
Lesson: a settings library that "loads `.env`" may only mean "into its own
model," not "into the process" — worth checking explicitly the first time
a new dependency needs to read a credential itself rather than through
your config object.

### Anticipated failure modes (not yet encountered)
Reference material only — **plausible failure modes based on how the
pieces work, not things that have actually happened.** Do not cite these
as real incidents in an interview. Any that do occur get promoted to the
"Real failures" section above with what actually happened.

- **Grading LLM returns prose with no extractable numbers.** Now handled
  by construction, not a try/except: `_parse_relevant_indices` degrades to
  an empty relevant set, which flows into the existing rewrite-then-retry
  path (or the "no context" answer after the rewrite cap) rather than
  needing special-case handling.
- **Rewrite loop converges to a paraphrase of the same query**, gaining
  nothing on the second retrieval pass — the rewrite cap bounds cost, but
  doesn't guarantee the rewritten query is actually better. A real
  eval (Phase 7) would be needed to measure how often this happens.
- **Guardrail false-positives on legitimate but obliquely-phrased research
  questions** (e.g. a question using no arXiv/paper-specific vocabulary
  but still in-scope), rejecting something it shouldn't. Single-LLM-call
  classification has no ground truth to check itself against here.
- **LLM API outage or rate limit mid-graph** — a transient failure on any
  of the 4 possible LLM calls would currently propagate as an unhandled
  exception up through the graph. The retry/backoff decorator from Phase 2
  (`src/services/retry.py`) is reused here, but a *sustained* outage still
  surfaces as a 5xx to the `/chat` caller — there's no circuit breaker or
  cached-fallback-answer behavior.
- **Provider swap changes behavior, not just cost** — switching
  `LLM_PROVIDER` from Anthropic to OpenAI mid-project could shift grading/
  guardrail judgment calls in ways that aren't obvious without re-running
  eval. The abstraction guarantees the *interface* is swappable, not that
  behavior is identical across providers.

## Tasks
- [x] Add `langgraph`, `anthropic`, `openai` to `pyproject.toml`; `uv sync`.
- [x] Extend `src/config.py`: `llm_provider`, `llm_model`, `llm_max_retries`,
      `max_rewrites`, `min_relevant_chunks`, `agent_retrieval_top_k`.
- [x] `src/services/llm.py` — `LLMClient` protocol, `AnthropicLLMClient`,
      `OpenAILLMClient`, `get_llm_client()` factory.
- [x] `src/agents/state.py` — `AgentState` TypedDict.
- [x] `src/agents/guardrail.py` — on-topic classification node.
- [x] `src/agents/retrieve.py` — hybrid-search node.
- [x] `src/agents/grade.py` — batched relevance-grading node.
- [x] `src/agents/rewrite.py` — query-rewrite node.
- [x] `src/agents/generate.py` — cited-answer generation node.
- [x] `src/agents/graph.py` — `build_graph(...)` factory with conditional
      routing (guardrail→retrieve/END, grade→generate/rewrite,
      rewrite→retrieve, generate→END).
- [x] `src/models/chat.py` — Pydantic `ChatRequest`/`ChatResponse`.
- [x] `src/routers/chat.py` — `POST /chat`.
- [x] `src/agent_cli.py` — CLI to run one query through the graph, print
      the trace and final answer.
- [x] Tests: `llm` clients (mocked HTTP), each node in isolation (fake LLM
      client / fake indices), full graph routing (guardrail reject path,
      rewrite-then-succeed path, rewrite-cap-exhausted path), `/chat`
      endpoint (mocked graph).
- [x] Live verification: full Compose stack up, real LLM API key, run
      `src/agent_cli.py` with a real question against the Phase 2/3 corpus,
      hit `POST /chat` over HTTP, inspect the trace, then
      `make lint && make test`.

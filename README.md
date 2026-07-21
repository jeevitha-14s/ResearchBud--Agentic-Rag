# arXiv Paper Curator

A rebuild of the [production-agentic-rag-course](https://github.com/jamwithai/production-agentic-rag-course)
architecture as a portfolio project: an agentic RAG system over arXiv papers,
with hybrid (BM25 + vector) search, LangGraph-based agent nodes, and a custom
evaluation harness comparing naive vs. agentic RAG.

See `CLAUDE.md` for the full architecture, deliberate deviations from the
reference project, and rationale. See `specs/` for a per-phase build log
(what was built, why, and what alternatives were considered) and
`DECISIONS.md` for the running architectural decision log.

Full setup and usage instructions land here in Phase 7 (deploy + polish).
Minimal current status: infra skeleton only (Phase 1) — see
`specs/01-infra-skeleton.md`.

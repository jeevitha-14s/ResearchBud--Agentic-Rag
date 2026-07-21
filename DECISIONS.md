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

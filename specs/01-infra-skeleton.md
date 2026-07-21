# Phase 1: Infra Skeleton

## 1. What's this?
The scaffolding everything else gets built on top of, with no domain logic
yet:
- Project layout (`src/`, `streamlit_app/`, `specs/`, tests) matching the
  structure in CLAUDE.md.
- `uv`-managed Python 3.12 project (`pyproject.toml`, lockfile).
- A FastAPI app with a single `/health` endpoint — enough to prove the
  container boots and responds.
- `docker-compose.yml` with exactly 3 services: `app`, `qdrant`, `redis`.
- Dev tooling wired up: Ruff (lint + format), MyPy (type checking),
  pre-commit hooks running both on commit.
- Pytest configured with one smoke test (`GET /health` returns 200).
- `.env.example` + `.gitignore` (so `.env` and API keys never get committed).
- `Makefile` with the commands already promised in CLAUDE.md (`make start`,
  `make lint`).

No ingestion, no search, no agents, no LLM calls yet — this phase is
"can I run `make start` and hit a health check" only.

## 2. Why this?
Every later phase (ingestion, search, agents, eval) needs a place to live and
a way to run and test itself. Getting the container stack, dependency
management, and code-quality gates right *first* means:
- Phase 2 onward is "add a module + a test," not "also figure out how Docker
  networking works."
- Linting/type-checking from commit #1 means later diffs stay reviewable
  instead of accumulating untyped code that's painful to retrofit.
- Qdrant and Redis are declared now (even though nothing uses them yet) so
  the Compose file's final shape — the thing under the "max 3 services"
  constraint — is settled early instead of getting renegotiated per phase.

## 3. Options I had
**Dependency manager:** `uv`, Poetry, plain `pip` + `requirements.txt`,
PDM.

**Project layout:** `src/` layout (import as `src.foo`, or installable
package) vs. flat layout (modules at repo root).

**Container strategy:** Docker Compose for app+deps, vs. running Qdrant/Redis
in Compose but the FastAPI app on the host (uvicorn --reload) during dev, vs.
no containers at all until deploy (Phase 7).

**Code quality enforcement:** pre-commit hooks (fail locally before commit)
vs. CI-only checks (GitHub Actions, no local gate) vs. no automated
enforcement (manual `make lint` only).

**Config/secrets handling:** `.env` + `python-dotenv`/`pydantic-settings`,
vs. plain `os.environ` reads scattered in code, vs. a config YAML file.

## 4. Why I chose what I chose
- **uv**: already fixed in CLAUDE.md's tech stack. It's also just faster
  and simpler than Poetry (single binary, no separate venv dance), and its
  lockfile behavior is the current default recommendation for new Python
  projects — a reasonable thing to defend in an interview as "current best
  practice," not just "what the course used."
- **`src/` layout**: prevents accidentally importing the installed package
  vs. the local checkout (a classic pytest footgun), and matches the
  `src/routers`, `src/services`, `src/models`, `src/agents` structure already
  specified in CLAUDE.md.
- **Docker Compose for all 3 services from day one**, including the app:
  running the *whole* stack in Compose from the start forces the app's
  Qdrant/Redis connection config (hostnames, ports) to be container-network-
  correct immediately, rather than working against `localhost` in dev and
  silently breaking when containerized later. `docker compose up` with a
  bind-mounted volume + `--reload` still gives fast dev iteration without
  giving up container-accurate networking.
- **pre-commit hooks**: catches lint/type issues before they're even
  committed, not just before merge. For a solo portfolio project without a
  CI reviewer, this is the enforcement mechanism, so it needs to be a local
  gate, not just a CI check that could be pushed around.
- **pydantic-settings for config**: type-safe env var loading, and it's
  already the natural choice given Pydantic is mandated for request/response
  schemas elsewhere in the stack — one validation library, not two.

## 5. Possible approaches & trade-offs
| Approach | Trade-off |
|---|---|
| **uv** (chosen) | Newer tool, smaller community track record than Poetry, but faster installs/resolution and a simpler mental model (no plugin ecosystem to learn). |
| Poetry | More mature, widely known in interviews, but slower and more ceremony (separate `poetry shell`/`poetry run` habits). |
| pip + requirements.txt | Zero learning curve, but no real lockfile discipline (hash pinning is manual/awkward) — weaker "production reproducibility" story. |
| **`src/` layout** (chosen) | Slightly more import-path ceremony (`src.services.foo` vs `services.foo`), but avoids the "tests silently import the wrong copy of the package" bug class. |
| Flat layout | Simpler imports, but the footgun above; also matches the reference course less well. |
| **Full stack in Docker Compose from day one** (chosen) | Dev loop is one layer removed from bare-metal Python (`docker compose up` instead of just `uvicorn --reload`), but avoids "works on my host, breaks in the container" surprises later. |
| App runs on host, only Qdrant/Redis in Compose | Faster/simpler local dev loop early on, but defers container-networking bugs to a later phase where they're more disruptive to isolate. |
| **pre-commit hooks** (chosen) | Adds a one-time setup step (`pre-commit install`) and a few seconds to every commit, but catches issues at the cheapest possible point — before they're even committed. |
| CI-only checks | No local friction, but for a solo project with no PR review step, "CI-only" means issues are caught only when I remember to check a dashboard, if at all. |
| **pydantic-settings** (chosen) | One more dependency, but type-checked, validated config beats untyped `os.environ.get()` calls scattered across modules. |
| Plain `os.environ` | Zero dependencies, but no validation, no defaults enforcement, and secrets/config handling becomes ad hoc per module. |

## 6. Common failure stories & fixes

**Python version drift.** `pyproject.toml` initially declared
`requires-python = ">=3.12"` — a floor, not a pin. This machine had no
system `python3.12`, so `uv sync` silently resolved against Python 3.13.13
instead. Nothing crashed; it just quietly wasn't the version CLAUDE.md
specifies. Fixed with `uv python install 3.12` + `uv python pin 3.12`,
which writes a `.python-version` file — `uv` reads that file and always
provisions/uses that exact interpreter regardless of what's on the host
PATH. Lesson: a `>=` constraint in `pyproject.toml` describes compatibility,
not the dev environment; pinning the actual dev interpreter needs a
separate mechanism (`.python-version`), otherwise "it works on my machine"
can mean two different Python versions on two machines.

**pre-commit install failed: not a git repo.** `pre-commit install` writes a
hook into `.git/hooks/`, so it hard-fails if there's no `.git` directory
yet. This project started as a bare folder with only `CLAUDE.md`. Fixed by
running `git init` before installing hooks — an ordering dependency that's
easy to miss since nothing in the spec's task list called out "git repo"
as a prerequisite.

**Docker healthcheck needs curl, which isn't in the base image.** The
`app` service's Compose healthcheck uses `curl -f http://localhost:8000/health`,
but the `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` base image doesn't
ship `curl` (it's a slim image). Fixed by adding an `apt-get install curl`
layer to the `Dockerfile`. Alternative considered: a Python-based
healthcheck (`python -c "urllib.request.urlopen(...)"`) to avoid the extra
apt layer entirely — deferred for now since curl is a common enough need
(future phases may want it for other checks) and the image size cost is
small, but worth reconsidering if image size becomes a real constraint.

**`.env` doesn't exist yet, but `docker-compose.yml` references it.**
`.env` is gitignored (per CLAUDE.md: never commit secrets) and wasn't
created as part of this phase — only `.env.example` was. Compose's
`env_file:` directive errors by default if the referenced file is missing.
Fixed with the Compose Spec's `required: false` option on the `env_file`
entry, so the stack still boots using the `environment:`-block defaults and
each service's own built-in defaults when no `.env` is present locally.

## Tasks
- [x] Scaffold `pyproject.toml` (Python 3.12, uv-managed) with initial deps:
      fastapi, uvicorn, pydantic-settings, ruff, mypy, pytest, pre-commit.
- [x] Create `src/` package structure: `src/routers/`, `src/services/`,
      `src/models/`, `src/agents/`, each with `__init__.py`.
- [x] Minimal FastAPI app (`src/main.py`) with `GET /health` → `{"status": "ok"}`.
- [x] `src/config.py` — pydantic-settings `Settings` class reading from `.env`.
- [x] `.env.example` and `.gitignore` (must exclude `.env`, `__pycache__`, `.venv`, etc.).
- [x] `Dockerfile` for the app (uv-based build).
- [x] `docker-compose.yml`: `app`, `qdrant`, `redis` services, app depends_on
      the other two, health check on `/health`.
- [x] Ruff + MyPy config in `pyproject.toml`.
- [x] `.pre-commit-config.yaml` running ruff (lint+format) and mypy.
- [x] `tests/test_health.py` — smoke test hitting `/health`.
- [x] `Makefile` with `start`, `lint`, and a `test` target.
- [x] `README.md` stub (project description, how to run — expanded later in Phase 7).

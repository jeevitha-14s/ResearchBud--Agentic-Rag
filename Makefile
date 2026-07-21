.PHONY: start stop lint test

start:
	docker compose up --build

stop:
	docker compose down

lint:
	uv run ruff check .
	uv run mypy src

test:
	uv run pytest

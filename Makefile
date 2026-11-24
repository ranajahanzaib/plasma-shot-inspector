.PHONY: setup dev test lint typecheck build data-bootstrap audit-demo

setup:
	uv sync --extra dev
	pnpm install

dev:
	@trap 'kill 0' EXIT INT TERM; uv run uvicorn plasma_inspector.api:app --app-dir src --host 127.0.0.1 --port 8000 & pnpm dev

test:
	uv run pytest

lint:
	uv run ruff check src tests

typecheck:
	uv run pyright
	pnpm typecheck

build:
	pnpm build

data-bootstrap:
	uv run plasma-inspector catalog search --level 2 --limit 10

audit-demo:
	uv run plasma-inspector audit run 30421 --level 2 --group summary

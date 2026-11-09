.PHONY: setup dev-api dev-web test test-api test-web lint typecheck contracts build

setup:
	.tooling/bin/uv sync --project apps/api --all-groups
	PATH="$$(dirname $$(command -v node)):$$PATH" pnpm install
	$(MAKE) contracts

dev-api:
	.tooling/bin/uv run --project apps/api uvicorn llm_gateway.main:app --reload --port 8000

dev-web:
	pnpm --filter @llm-gateway/web dev

test: test-api test-web

test-api:
	cd apps/api && ../../.tooling/bin/uv run pytest

test-web:
	pnpm --filter @llm-gateway/web test

lint:
	.tooling/bin/uv run --project apps/api ruff check apps/api

typecheck:
	pnpm --filter @llm-gateway/web typecheck

contracts:
	.tooling/bin/uv run --project apps/api python scripts/export_openapi.py
	pnpm --filter @llm-gateway/web contracts

build:
	pnpm --filter @llm-gateway/web build
	.tooling/bin/uv build --project apps/api

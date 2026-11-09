# Orbit LLM Gateway

A frontend and backend monorepo for a text-only LLM gateway. DeepSeek
`deepseek-chat` is the primary candidate, with OpenAI and Anthropic available as
fallbacks in the example routing table.

## What is included

- React 19 + Vite + TypeScript + Ant Design 6 chat workspace.
- Interactive architecture page with startup, request, fallback, and persistence flows.
- OpenAI-compatible `POST /v1/chat/completions`.
- OpenAI Responses-compatible `POST /v1/responses` for the text-only subset.
- YAML provider/model/route configuration with `${ENV_VAR}` interpolation.
- Ordered candidate fallback and JSON Schema validation for non-streaming calls.
- Bearer API-key identity and per-key fixed-window rate limiting.
- SQLite request, attempt, trace, and token-usage records.
- Model routing and usage query pages.

The first release does not support tools, images, background responses, or
`previous_response_id`.

## Prerequisites

- Node 22 and pnpm 11.
- Python 3.13 and uv 0.13.

The repository-local `.tooling` environment is used by `make` to invoke uv.
Create it once if it is absent:

```bash
python3.13 -m venv .tooling
.tooling/bin/python -m pip install uv
```

## Setup

```bash
cp .env.example .env
make setup
```

Set `DEEPSEEK_API_KEY` in `.env` to enable the primary provider. Without it, the
service still starts and the frontend remains available; DeepSeek candidates are
marked as missing a key and routing continues to any configured fallback.

The example config uses `local-dev-key` as the development gateway key. Replace
it through `GATEWAY_API_KEY` before sharing an environment.

## Development

Run the API:

```bash
make dev-api
```

Run the frontend in another terminal:

```bash
make dev-web
```

Open `http://localhost:5173`, choose **连接网关**, and enter the configured
gateway key. The browser stores the key only in `sessionStorage`.

## Configuration

`GATEWAY_CONFIG_FILE` selects a YAML file. If it is unset, the API loads
`apps/api/config/gateway.example.yaml`. An explicitly configured but missing
file is an error.

Strings support:

```text
${VARIABLE}
${VARIABLE:-fallback}
```

Provider keys may default to an empty string so the service can start in a
read-only/degraded mode. A route's candidates are tried in declaration order.

## API summary

```text
POST /v1/chat/completions
POST /v1/responses
GET  /api/v1/models
GET  /api/v1/usage/summary
GET  /api/v1/usage/calls
GET  /api/v1/usage/calls/{request_id}
GET  /healthz
GET  /readyz
```

The two generation endpoints require `Authorization: Bearer <gateway-key>`.
Model names in requests are route aliases such as `default` or `fast-chat`.

## Quality checks

```bash
make test
make lint
make typecheck
make build
```

To refresh the generated OpenAPI document and frontend types:

```bash
make contracts
```

## Docker

```bash
docker compose up --build
```

The frontend is exposed on port `5173`; the API is exposed on port `8000`.

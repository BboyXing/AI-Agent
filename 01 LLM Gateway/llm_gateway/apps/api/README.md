# LLM Gateway API

FastAPI service for OpenAI-compatible text generation with ordered model
candidate fallback, API-key identity, in-memory rate limiting, SQLite usage
records, and structured trace logs.

Configuration is loaded from `GATEWAY_CONFIG_FILE`, or from
`config/gateway.example.yaml` when the variable is unset.

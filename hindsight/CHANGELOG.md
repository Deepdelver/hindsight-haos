# Changelog

## 1.0.5

- Rebuild on the Debian base image (`hassio-addons/debian-base`) instead of Alpine
- Adopt the standard HAOS addon layout: S6 `cont-init.d` + `services.d`, `build.json`, `apparmor.txt`
- Add `env_vars` passthrough so any `HINDSIGHT_API_*` variable can be set from the UI
- Install PostgreSQL 15 and pgvector from the PGDG repository
- Install `hindsight-api-slim` into an isolated venv (no local ML models)
- Default embeddings to OpenAI `text-embedding-3-small`, reranker to `rrf`
- Secrets typed as `password` so the Supervisor masks them
- Healthcheck against the API port

## 1.0.4

- Correct `webui` port template (no `/tcp` suffix) and base image reference

## 1.0.3

- Switch to the slim image, external embeddings, `rrf` reranker

## 1.0.2

- Clean up `config.yaml` for Supervisor compatibility

## 1.0.1

- Add LLM, embeddings, reranker, MCP, worker and log-level options

## 1.0.0

- Initial release

# Changelog

## 1.1.0

- Add the Hindsight Control Plane as a separate, menu-selectable service
  (`control_plane` on/off, `control_plane_port` for its port)
- Install Node.js 22 and `@vectorize-io/hindsight-control-plane` from npm
- Bind the control plane as `localhost` with `--dns-result-order=ipv4first`,
  the workaround for the Next.js loopback redirect defect (#1926)
- Drop the invented `HINDSIGHT_API_MCP_LOCAL_BANK_ID`, `HINDSIGHT_API_CONTROL_PLANE_PORT`
  and `HINDSIGHT_API_DATA_DIR` variables — the bank is part of the MCP URL path
- Healthcheck now probes `/health`
- Start period raised to 180s for the first-run model and database setup

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

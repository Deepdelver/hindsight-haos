# Changelog
## 1.2.18

- Pin the Control Plane to `@vectorize-io/hindsight-control-plane` 1.2.3 to match hindsight-api 1.2.3, fixing UI/API version-mismatch 404s and empty Memories/Experience/Observations tabs

## 1.2.17

- Send no-store cache headers for the Control Plane so stale UI assets cannot survive an update

## 1.2.16

- Serve the dashboard on two ports: direct access on 9999 without rewriting, ingress on 9997 with path rewriting

## 1.2.15

- Force full page reloads for programmatic navigation too, so bank creation opens the new bank instead of a Next.js error

## 1.2.14

- Stop rewriting double-quoted route fragments that corrupted API URLs with duplicate ingress prefixes, fixing bank creation and bank pages

## 1.2.13

- Force full page loads for internal links so Next.js client routing does not break under ingress

## 1.2.12

- Rewrite the bank-selector path regex so a bank opens after clicking it in the sidebar


## 1.2.11

- Rewrite client-side navigation routes too, so clicking a bank opens it inside ingress
  instead of navigating to a Home Assistant 404

## 1.2.10

- Wrap the generated nginx config in `events`/`http` blocks so nginx actually starts

## 1.2.9

- Rewrite the Control Plane's root-absolute asset/API paths at runtime through nginx,
  using the ingress path from the Supervisor. Fixes broken images, assets and bank
  create/click in the Home Assistant sidebar
- Document the Hermes memory plugin in `local_external` mode in the README and addon docs

## 1.2.8

- Remove the leading slash from `ingress_entry` so the sidebar URL has no double slash
  and opens `/dashboard` directly

## 1.2.7

- Set `ingress_entry: /dashboard` so the sidebar panel opens the Control Plane directly
  instead of following the root 307 redirect into Home Assistant's main panel

## 1.2.6

- Add a `mode` switch. `simple` (default) ignores all provider/model options and uses
  the free local stack with automatic models; `expert` passes all options through for
  subscriptions, Ollama, or self-hosted models
- Document both modes in the README and addon docs

## 1.2.5

- Bind the Control Plane to `0.0.0.0` so Supervisor's port mapping and ingress can
  reach port 9999

## 1.2.4

- Add the official Hindsight icon as the addon icon (`icon.png`)
- Enable ingress so the Control Plane dashboard opens from the Home Assistant sidebar
  (`ingress_port: 9999`, `panel_title: Hindsight`)
- Add a watchdog health check on the API `/health` endpoint
- Link the official Hindsight project and credit Deepdelver in the description, README
  and addon docs

## 1.2.3

- Source the generated env with `set -a` so `hindsight-api` actually receives the
  LLM, embeddings and reranker settings instead of falling back to provider defaults
- Create the database and enable pgvector after PostgreSQL is accepting connections

## 1.2.2

- Make embeddings and reranker model selection automatic by default. `embeddings_model`
  and `reranker_model` now default to `auto`, which leaves the model id unset so
  Hindsight uses (and downloads) its own provider default. An explicit model id in the
  Configuration tab still overrides it
- Document how to opt into `hindsight-ai/hs-embed-1` and the re-embed requirement
  when switching models on an install that already holds memories

## 1.2.1

- Keep `next` in the control plane bundle and clean up stale PostgreSQL PID files on
  restart

## 1.2.0

- Zero-config local models: built-in llama.cpp LLM plus local ONNX embeddings and
  reranker, so no API key or external model server is needed with the defaults
- Fix the PostgreSQL user switch during cluster init

## 1.1.1

- Remove the `image:` key so the Supervisor builds locally from the Dockerfile;
  the referenced GHCR images do not exist and would make install fail.

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

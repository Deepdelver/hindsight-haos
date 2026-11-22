# Hindsight AI Memory for Home Assistant OS

Hindsight is a persistent AI memory engine that gives your AI agents long-term memory with **retain**, **recall**, and **reflect** APIs. It runs as a standalone service on your Home Assistant, accessible to all your AI agents via MCP (Model Context Protocol).

Addon created and maintained by [Deepdelver](https://github.com/Deepdelver). Hindsight itself is an independent open-source project: [documentation](https://hindsight.vectorize.io/developer/) · [source](https://github.com/vectorize-io/hindsight) · [this addon](https://github.com/Deepdelver/hindsight-haos).

## What it does

- **Retain** — Store facts, preferences, and context from conversations
- **Recall** — Retrieve relevant memories using semantic search
- **Reflect** — Synthesize insights from accumulated memories

## Setup

1. Install this addon
2. Go to **Configuration** and pick a mode:
   - **simple** (default) — local LLM + local ONNX embeddings/reranker, no keys, nothing else to set
   - **expert** — configure the providers and models yourself (see below)
3. In expert mode, set:
   - **llm_provider** — `openai`, `anthropic`, `gemini`, `groq`, `deepseek`, `ollama`, `fireworks`, `openrouter`, `nous`. Do not pick `custom`: the API rejects it (see Troubleshooting); for a gateway use `openai` plus `llm_base_url`.
   - **llm_api_key** — API key for the chosen provider (not needed for `ollama`)
   - **llm_model** — Model name (default `gemma-4-e2b-it`)
   - **llm_base_url** — Custom endpoint for Ollama or an OpenAI-compatible proxy (default empty; set it in the Configuration tab; expert mode only)
   - **embeddings_provider** — `onnx` (local, no key), or `local`, `openai`, `cohere`, `tei`, ...
   - **embeddings_model** — `auto` (default: let Hindsight choose and download its model), or an explicit model id
   - **embeddings_api_key** — Separate key for embeddings (falls back to `llm_api_key`)
   - **reranker_provider** — `onnx` (local, no key), `rrf` (no model), or `cohere`, `flashrank`, ...
   - **reranker_model** — `auto` (default) or an explicit model id
   - **mcp_enabled** — `true`/`false`, expose the MCP server
   - **control_plane** — `true`/`false`, run the web UI on port 9999
   - **control_plane_port** — port for the web UI (default `9999`)
   - **worker_id** — Stable identity across restarts (default `hindsight-haos`)
   - **log_level** — `debug`, `info`, `warning`, `error`
4. Start the addon

## Configuration options

Every option is also exported as an environment variable, and the **env_vars** list
lets you set any additional variable directly:

| Option | Environment variable |
| --- | --- |
| `mode` | (addon option: `simple` or `expert`) |
| `llm_provider` | `HINDSIGHT_API_LLM_PROVIDER` |
| `llm_api_key` | `HINDSIGHT_API_LLM_API_KEY` |
| `llm_model` | `HINDSIGHT_API_LLM_MODEL` |
| `llm_base_url` | `HINDSIGHT_API_LLM_BASE_URL` |
| `embeddings_provider` | `HINDSIGHT_API_EMBEDDINGS_PROVIDER` |
| `embeddings_model` | `HINDSIGHT_API_EMBEDDINGS_<PROVIDER>_MODEL*` |
| `embeddings_api_key` | `HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY` (for `openai`) |
| `reranker_provider` | `HINDSIGHT_API_RERANKER_PROVIDER` |
| `reranker_model` | `HINDSIGHT_API_RERANKER_ONNX_MODEL_ID` / `..._FLASHRANK_MODEL` |
| `mcp_enabled` | `HINDSIGHT_API_MCP_ENABLED` |
| `control_plane` | (addon service toggle, not a Hindsight variable) |
| `control_plane_port` | `PORT` / `HINDSIGHT_CP_PORT` for the UI service |
| `worker_id` | `HINDSIGHT_API_WORKER_ID` |
| `log_level` | `HINDSIGHT_API_LOG_LEVEL` |

Add a custom variable in the UI under **env_vars**, for example:

```
name:  HINDSIGHT_API_VECTOR_EXTENSION
value: pgvector
```

### Simple and expert mode

`mode: simple` forces the local stack regardless of the other fields: llama.cpp LLM
(`gemma-4-e2b-it`), ONNX embeddings and ONNX reranker, all models `auto`. No key is
needed. It is the recommended setting for a fresh install.

`mode: expert` passes every option through: LLM provider/model/key/base URL,
embeddings provider/model/key, reranker provider/model, and the llama.cpp path,
context size and GPU layers. Use it for subscriptions (OpenAI, Anthropic, OpenRouter,
...), Ollama on your LAN, or self-hosted models. `env_vars` still works in both modes.

### Automatic model selection

`embeddings_model` and `reranker_model` default to `auto`. The addon then writes only
`HINDSIGHT_API_EMBEDDINGS_PROVIDER` / `HINDSIGHT_API_RERANKER_PROVIDER` and leaves the
model id unset, so Hindsight uses its own default for that provider and downloads it
from Hugging Face on first start. Upstream default changes take effect on update
without an addon change.

Set an explicit model id to pin one. The addon maps it to the correct variable for the
selected provider:

| Provider | Embeddings variable | Reranker variable |
| --- | --- | --- |
| `onnx` | `..._EMBEDDINGS_ONNX_MODEL_ID` | `..._RERANKER_ONNX_MODEL_ID` |
| `local` | `..._EMBEDDINGS_LOCAL_MODEL` | — |
| `openai` | `..._EMBEDDINGS_OPENAI_MODEL` | — |
| `flashrank` | — | `..._RERANKER_FLASHRANK_MODEL` |

Other providers use their own Hindsight defaults; set provider-specific variables via
`env_vars` if needed. With `onnx`, an explicit model must be a Hugging Face repo that
contains `onnx/model.onnx`. Hindsight recommends `hindsight-ai/hs-embed-1` for agent
memory; that model needs no query/passage prefix, so clear both defaults:

```
name:  HINDSIGHT_API_EMBEDDINGS_ONNX_QUERY_PREFIX
value: ""
name:  HINDSIGHT_API_EMBEDDINGS_ONNX_PASSAGE_PREFIX
value: ""
```

Vectors from different models do not mix. If the install already holds memories, run
`hindsight-admin reembed` after switching models.

## Connecting your AI agents

Once running, Hindsight exposes an MCP server at:

```
http://<your-home-assistant-ip>:8888/mcp/<bank_id>/
```

### Hermes Agent

The recommended integration is the official Hindsight **memory provider** plugin in
`local_external` mode:

```bash
hermes plugins install hindsight --enable --yes-deps
hermes config get memory.provider          # hindsight
hermes memory status                       # Provider: hindsight, Status: available
```

Create `$HERMES_HOME/hindsight/config.json` (`~/.hermes/hindsight/config.json` for the
default profile):

```json
{
  "mode": "local_external",
  "api_url": "http://9b734b76-hindsight:8888",
  "bank_id": "hermes",
  "recall_min_scores": { "reranker": 0.25 }
}
```

Use the addon hostname from **Settings → Apps → Hindsight → Hostname** (unique per
installation), or `http://<ha-ip>:8888` from another machine. No API key is needed.
Restart a running gateway with `hermes gateway restart`. The `hermes` bank is created on
the first retain; `recall_min_scores.reranker` filters off-topic recalls on small banks.
Full reference: https://hindsight.vectorize.io/sdks/integrations/hermes

The MCP endpoint is an alternative for clients that don't use the memory plugin:

```bash
hermes config set mcp_servers.hindsight.url "http://<ha-ip>:8888/mcp/hermes/"
```

### OpenClaw / Claude Code

```bash
claude mcp add --transport http hindsight http://<ha-ip>:8888/mcp/default/
```

### OpenCode / Cursor / any MCP client

```json
{
  "mcpServers": {
    "hindsight": {
      "url": "http://<ha-ip>:8888/mcp/default/"
    }
  }
}
```

## Web UI

The Hindsight Control Plane is available at:

```
http://<your-home-assistant-ip>:9999
```

Use it to browse memories, manage banks, and monitor the system.

It also appears as a **Hindsight** item in the Home Assistant sidebar. Ingress runs on internal port **9997** (port 9999 is the direct UI); Home Assistant proxies the panel under `/api/hassio_ingress/.../`, so you can open it from the sidebar on any device without exposing port 9999. The addon
page has **Auto update** and **Watchdog** toggles; the watchdog checks
`http://[HOST]:[PORT:8888]/health` and restarts the addon if it stops responding.

## Ports

- **8888** — Hindsight API and MCP server
- **9999** — Control Plane web UI (direct/LAN access)
- **9997** — internal ingress port used by the Home Assistant sidebar; no port forwarding is needed for the UI

## Data

PostgreSQL data lives in `/data` inside the addon container and is included in
Home Assistant backups. The addon uses a cold backup, so Home Assistant stops it
while the backup runs.

The add-on updates automatically when a new version is published. Upstream API
and UI versions are recorded in `hindsight/versions.json` and compared daily by
`scripts/check_versions.py`; drift opens a review task instead of silently
changing a running add-on.

## Using with Ollama

If you run the Ollama addon on the same Home Assistant:

- **llm_provider**: `ollama`
- **llm_api_key**: leave empty
- **llm_model**: your model, e.g. `qwen3.5:latest`
- **llm_base_url**: `http://homeassistant.local:11434`
- **embeddings_provider**: `onnx` (local) — `ollama` is not a valid value in this add-on's schema; keep the local ONNX embeddings or pick a supported provider such as `local` / `openai`

## Using an OpenAI-compatible gateway (OmniRoute, LiteLLM, ...)

For a local gateway that aggregates many model providers behind one endpoint:

- **mode**: `expert`
- **llm_provider**: `openai` — do NOT use `custom` here. `custom` is an add-on
  schema value but the Hindsight API rejects it (`ValueError: Invalid LLM provider:
  custom`) and the add-on crash-loops. `openai` speaks the OpenAI-wire format
  that OmniRoute/LiteLLM expose.
- **llm_api_key**: the gateway's API key (stored per-install, never in the repo)
- **llm_model**: a routing alias such as `auto/best-free`, if your gateway supports it
- **llm_base_url**: the gateway's OpenAI-compatible base URL, e.g. `http://<host>:20128/api/v1`
- **embeddings_provider**: `onnx` — keep embeddings local even when the LLM is remote

## Troubleshooting

- **Retains stop silently / `402 Insufficient Balance` or `429` in the addon log** —
  fact extraction is mandatory: if the configured LLM provider is out of credits or
  rate-limited, **every retain fails** and no new memories are stored, while recall
  keeps working (the dashboard still shows old "last activity"). Fix the extraction
  LLM: either switch `mode` to `simple` (local models, no key), or point
  `llm_base_url` at a gateway whose `llm_model` fails over across providers (e.g.
  a `combo` alias). Watch `last_write_at` on the bank to confirm retains resume.
- **Addon does not appear in the store** — the Supervisor silently drops apps whose
  `config.yaml` fails validation. Check **Settings > System > Logs > Supervisor**
  for a line starting `Can't read .../config.yaml`.
- **Container exits at start** — check the addon log. The most common cause is an
  empty `llm_api_key` with a provider that requires one.
- **Add-on crash-loops with `ValueError: Invalid LLM provider: custom`** —
  `custom` appears in the add-on's provider dropdown but the Hindsight API
  rejects it. Select `openai` and set `llm_base_url` to your OpenAI-compatible
  gateway (see above); leave `embeddings_provider` on `onnx`.
- **MCP endpoint refuses connections** — confirm port 8888 is published and that
  `mcp_enabled` is `true`.
- **`Client Error / HTTP 404` in the web UI** — verify the pinned Control Plane version
  in `Dockerfile` matches the `hindsight-api` version from `/version`, run
  `python3 hindsight/tests/test_ingress_rewrite.py`, then hard-refresh the browser.
- **Cannot select a bank from the sidebar UI** — the bank-selector regex rewrite is
  missing from `nginx.conf.template`; the regression test above catches this.
- **Retains retry with `429 Too Many Requests`** — the configured LLM provider is
  rate-limiting fact extraction (common with free hosted models). Use `mode: simple`
  for local models or a provider key with a higher quota; the worker retries safely.
- **Daily version-watch task keeps reopening** — `scripts/check_versions.py`
  compares `hindsight/versions.json` and the Dockerfile pin with npm/PyPI. When
  upstream moves it opens one idempotent review task; it never changes the
  running add-on. Run `python3 scripts/check_versions.py` for the current
  comparison, then bump the API and UI pins together in a normal release.
- **`git push` blocked by the pre-push gate** — the Kanban assessment task for the
  current change set (key printed by the hook) must be `done` and all four
  regression suites in `hindsight/tests/` must pass (`test_source_defaults.py`,
  `test_ingress_rewrite.py`, `test_prepush_pipeline.py`, `test_version_watch.py`).
  Run `scripts/setup-hooks.sh global` once per machine; see README → Development
  and testing for the full flow.

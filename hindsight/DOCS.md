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
   - **llm_provider** — `openai`, `anthropic`, `gemini`, `groq`, `deepseek`, `ollama`, `fireworks`, `openrouter`, `nous`. `custom` is kept for existing installs and is mapped to `openai` by the add-on (it requires `llm_base_url`); for a gateway prefer `openai` plus `llm_base_url` directly.
   - **llm_api_key** — API key for the chosen provider (not needed for `ollama`, or for `custom` pointing at a keyless gateway)
   - **llm_model** — Model name (default `gemma-4-e2b-it`)
   - **llm_base_url** — Custom endpoint for Ollama or an OpenAI-compatible proxy (default empty; set it in the Configuration tab; expert mode only)
   - **consolidation_llm_provider** — Expert only: separate provider for observation consolidation (default empty = reuse `llm_provider`)
   - **consolidation_llm_model** — Expert only: separate consolidation model (default empty = reuse `llm_model`)
   - **consolidation_llm_base_url** — Expert only: separate consolidation endpoint (default empty = reuse `llm_base_url`)
   - **consolidation_llm_api_key** — Expert only: key for the consolidation provider (default empty = reuse `llm_api_key`)
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

## Version compatibility

This add-on pins both upstream components to **1.3.0**:
`hindsight-api-slim[local-llm,local-onnx]==1.3.0` from PyPI and
`@vectorize-io/hindsight-control-plane@1.3.0` from npm. Both 1.3.0 packages were
published on 2026-11-24 from the same upstream `Release v1.3.0` commit
(`937886199e0e…`). API and Control Plane must stay in sync — a mismatch causes
404s and empty memory tabs. The pair is recorded in `hindsight/versions.json` and
compared daily by `scripts/check_versions.py`. No configuration key was removed or
renamed in 1.3.0; the release does ship migration work and enables knowledge banks
by default, so the first start after upgrading from 1.2.3 can take longer. Wait for
`/health` before using the UI.

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
| `consolidation_llm_provider` | `HINDSIGHT_API_CONSOLIDATION_LLM_PROVIDER` |
| `consolidation_llm_model` | `HINDSIGHT_API_CONSOLIDATION_LLM_MODEL` |
| `consolidation_llm_base_url` | `HINDSIGHT_API_CONSOLIDATION_LLM_BASE_URL` |
| `consolidation_llm_api_key` | `HINDSIGHT_API_CONSOLIDATION_LLM_API_KEY` |
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

### Dedicated consolidation LLM (since 1.2.26)

Hindsight 1.3.0 can route observation consolidation separately from retain. The
add-on exposes that through four expert-mode options:

| Option | Upstream variable | Fallback when empty |
| --- | --- | --- |
| `consolidation_llm_provider` | `HINDSIGHT_API_CONSOLIDATION_LLM_PROVIDER` | `HINDSIGHT_API_LLM_PROVIDER` |
| `consolidation_llm_model` | `HINDSIGHT_API_CONSOLIDATION_LLM_MODEL` | `HINDSIGHT_API_LLM_MODEL` |
| `consolidation_llm_base_url` | `HINDSIGHT_API_CONSOLIDATION_LLM_BASE_URL` | `HINDSIGHT_API_LLM_BASE_URL` |
| `consolidation_llm_api_key` | `HINDSIGHT_API_CONSOLIDATION_LLM_API_KEY` | `HINDSIGHT_API_LLM_API_KEY` |

`30-config.sh` emits a variable only when its option is non-empty, so a partial
override is fine: set just `consolidation_llm_model` and the provider, key and base
URL stay on the normal LLM route. All four defaults in `config.yaml` are `""`, so
an upgrade writes no new variable and behaviour is unchanged. In `simple` mode all
four are reset to empty before the env file is written, so a value left over from
an expert setup cannot turn a local-only install into a remote caller. For a
gateway use `openai` (not `custom`) plus `consolidation_llm_base_url`.

This is an operational **throughput** fix for the consolidation backlog. It does
not change recall quality, fix a failing retain, or remove pending memories. The
measured prompts on this host were large enough (52,758 characters, ~14k–16k input
tokens) that `combo` and `grok-4.7` both exceeded 240 s and `auto/best-free` timed
out at 150 s during extraction; `google/gemini-2.5-flash-lite` returned 401 because
no key was configured. Measure any candidate against the real prompt before
committing it, and bound the prompt with the per-bank limits below.

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
- **llm_provider**: `openai` (recommended) or `custom`. Since 1.2.24 the add-on
  maps `custom` to `openai` automatically, because the Hindsight API itself
  rejects `custom` (`ValueError: Invalid LLM provider: custom`). `custom`
  requires a non-empty `llm_base_url`; without it the add-on stops at startup
  with a clear error. `openai` speaks the OpenAI-wire format that
  OmniRoute/LiteLLM expose.
- **llm_api_key**: the gateway's API key (stored per-install, never in the repo).
  Optional with `custom` for a keyless gateway: the add-on then sends a fixed
  placeholder key (`local`). A gateway that enforces auth needs a real key.
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
- **Container exits at start** — check the addon log. Common causes: an empty
  `llm_api_key` with a provider that requires one, or `llm_provider: custom`
  without `llm_base_url` (the log says exactly which option is missing).
- **Add-on crash-loops with `ValueError: Invalid LLM provider: custom`** —
  fixed in 1.2.24: `custom` is now mapped to `openai` (requires `llm_base_url`).
  Update the add-on; on older versions select `openai` and set `llm_base_url`
  to your OpenAI-compatible gateway (see above); leave `embeddings_provider`
  on `onnx`. The startup log shows `LLM: openai / <model>` after the mapping.
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
  current change set (key printed by the hook) must be `done` and all five
  regression suites in `hindsight/tests/` must pass (`test_source_defaults.py`,
  `test_ingress_rewrite.py`, `test_prepush_pipeline.py`, `test_version_watch.py`,
  and `test_continit_providers.py`).
  Run `scripts/setup-hooks.sh global` once per machine; see README → Development
  and testing for the full flow.

### Growing Observations / Pending count (consolidation backlog)

A rising **Observations** count with many `consolidation_state=pending` memories
means the LLM extractor cannot keep up, not that the add-on is broken. In the
2026-11-26 incident bank `hermes` held 1566 pending memories: the `auto/best-fast`
alias on OmniRoute failed over through dead providers (502/404/400, 60–115 s per
call) and consolidation on 14k-token prompts took 110–327 s. The runtime fix was a
working `combo` extraction route plus tighter per-bank consolidation limits; no
source change was needed. Since 1.2.26, expert installs can additionally separate
the consolidation route with the four `consolidation_llm_*` options above; they
are empty by default and are a throughput lever, not a recall fix.

Diagnose before changing anything:

1. `GET /v1/default/banks/<bank>/memories/list?consolidation_state=pending&limit=1`
   — read `total` for the backlog size; `GET /v1/default/banks/<bank>/stats` shows
   `pending_consolidation` / `failed_consolidation`.
2. `GET /v1/default/banks/<bank>/operations?type=consolidation&limit=20` — check
   `status`, `error_message`, `retry_count` and `progress.total` for stuck work.
3. `GET /v1/default/banks/<bank>/llm-requests?limit=20` — check `provider`,
   `model`, `status` and `duration_ms` for the failing calls.

A dead extraction route leaves `/health` green and shows provider `502/404/400`
statuses with slow traces (tens of seconds to ~5 minutes). The earlier OmniRoute
heap-503 was different: the gateway returned `503` for every route at once with
heap/OOM pressure in its own log, and had to be recovered at the gateway level
first. Do not confuse the two.

Safe mitigations (runtime only; keep the repository config credential-free):

- Use the add-on **env_vars** to select a working route/model, e.g.
  `{name: HINDSIGHT_API_LLM_MODEL, value: combo}` (plus gateway URL/key if used).
  Keep `mode: simple`, `llm_provider: llamacpp` and empty `llm_api_key` /
  `llm_base_url` in the source defaults; override only in installed options.
- Tighten per-bank consolidation with the `updates` wrapper (example values tune
  to your context window):

  ```bash
  curl -X PATCH 'http://<ha-ip>:8888/v1/default/banks/<bank>' \
    -H 'Content-Type: application/json' \
    -d '{"updates":{
          "consolidation_max_memories_per_round": 10,
          "consolidation_llm_parallelism": 2,
          "consolidation_source_facts_max_tokens": 4000
        }}'
  ```

Watch `pending_consolidation` drop while `total_observations` grows. **Never delete
pending memories to clear the backlog** — consolidation regenerates observations
from them, so deletion destroys derived knowledge permanently. Failed operations
can be retried from the Operations screen (`POST .../operations/{id}/retry`) once
the route is healthy.

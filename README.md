# Hindsight HAOS

Home Assistant OS addon for [Hindsight](https://hindsight.vectorize.io/) — persistent AI agent memory with retain, recall, and reflect APIs.

Created and maintained by [Deepdelver](https://github.com/Deepdelver). This is an unofficial addon; the Hindsight project itself lives at [hindsight.vectorize.io](https://hindsight.vectorize.io/) and [github.com/vectorize-io/hindsight](https://github.com/vectorize-io/hindsight).

Official project links:

- Documentation: https://hindsight.vectorize.io/developer/
- Source: https://github.com/vectorize-io/hindsight
- This addon: https://github.com/Deepdelver/hindsight-haos

## Installation

1. In Home Assistant, go to **Settings** > **Apps** > **⋮** (top right) > **Repositories**
2. Add this repository URL: `https://github.com/Deepdelver/hindsight-haos`
3. Click **Install app** and find **Hindsight** in the list
4. Start the addon — no API key or external model server is needed with the defaults
5. On first start it downloads a small local LLM (~3.5 GB) and ONNX models; allow a few minutes

The first install builds the container on your Home Assistant (PostgreSQL 15, pgvector, the Hindsight API with local model support, and Node for the UI), so allow a few minutes.

## What is Hindsight?

Hindsight gives your AI agents persistent memory that works across all your tools — Hermes Agent, OpenClaw, OpenCode, Cursor, Claude Code, and any MCP-compatible client. Store context in one agent, retrieve it in another.

- **API Server**: Port 8888 (REST + MCP)
- **Control Plane**: Port 9999 (Web UI)
- **MCP endpoint**: `http://<your-ha-ip>:8888/mcp/<bank_id>/`

### Dashboard in the sidebar

The Control Plane web UI is available as a panel in the Home Assistant sidebar
(**Hindsight**). Ingress is enabled in `config.yaml`, so Home Assistant proxies it at
`https://<your-ha-host>/api/hassio_ingress/.../` — no port forwarding needed. The
**Watchdog** toggle restarts the addon if the API health check on port 8888 stops
answering, and **Auto update** keeps it current with this repository. Both toggles are
on the addon's page in Home Assistant; the watchdog URL is defined in `config.yaml`.

## Configuration

| Option | Default | Purpose |
| --- | --- | --- |
| `llm_provider` | `llamacpp` | LLM provider. `llamacpp` runs a small local model inside the addon — no key. Change to `openai`, `ollama`, `groq`, `anthropic`, ... for a different one |
| `llm_api_key` | — | Only needed for hosted providers |
| `llm_model` | `gemma-4-e2b-it` | Model name (default model for the chosen provider) |
| `llm_base_url` | — | Custom endpoint (Ollama, OpenAI-compatible proxies) |
| `embeddings_provider` | `onnx` | Local ONNX embeddings, no key. Hosted: `openai`, `cohere`, `tei`, ... |
| `embeddings_model` | `auto` | `auto` lets Hindsight pick and download its default model. Set a model id to override |
| `reranker_provider` | `onnx` | Local ONNX reranker, no key. `rrf` needs no model at all |
| `reranker_model` | `auto` | `auto` lets Hindsight pick its default model; set a model id to override |
| `llamacpp_model_path` | — | Optional GGUF path; otherwise auto-downloaded to `/data/hindsight-home/.hindsight/models` |
| `llamacpp_context_size` | `16384` | Local LLM context window |
| `llamacpp_gpu_layers` | `0` | GPU layers (`0` = CPU, `-1` = all) |
| `mcp_enabled` | `true` | Expose the MCP server |
| `control_plane` | `true` | Run the web UI (port 9999) |
| `control_plane_port` | `9999` | Port for the web UI |
| `worker_id` | `hindsight-haos` | Stable worker identity |
| `log_level` | `info` | Log verbosity |

An **env_vars** list is available for any additional `HINDSIGHT_API_*` variable.

### Automatic embeddings models

`embeddings_model` and `reranker_model` default to `auto`. In that mode the addon sets
only the provider and lets Hindsight choose its own model — it downloads the weights on
first start and picks up upstream default changes on update. Set an explicit model id
when you want to pin one; it is then passed to the selected provider (ONNX, local,
OpenAI, FlashRank — see the table below).

For the `onnx` provider an explicit model must be a Hugging Face repo containing
`onnx/model.onnx`. Hindsight currently recommends `hindsight-ai/hs-embed-1` for agent
memory. It needs no E5 query/passage prefix, so clear both when selecting it:

```
embeddings_model: hindsight-ai/hs-embed-1
env_vars:
  - name: HINDSIGHT_API_EMBEDDINGS_ONNX_QUERY_PREFIX
    value: ""
  - name: HINDSIGHT_API_EMBEDDINGS_ONNX_PASSAGE_PREFIX
    value: ""
```

Both models yield 384-dimensional vectors, but vectors from different models do not
mix. On an install that already has memories, run `hindsight-admin reembed` after
changing the model; a fresh install needs nothing.

Hindsight always uses an LLM for fact extraction, consolidation and reflect. The defaults keep that local and free: built-in llama.cpp plus local ONNX embeddings/reranking. Switching `llm_provider` to a hosted provider needs the matching `llm_api_key`; switching `embeddings_provider`/`reranker_provider` to a hosted one needs its key (an `env_vars` entry such as `HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY=...`). Local models are slower and lower quality than a hosted model — pick what fits your hardware.

## Layout

```
hindsight/
├── config.yaml          # addon metadata, options schema, ports
├── build.json           # base image per architecture
├── Dockerfile           # Debian base + PostgreSQL 15 + pgvector + hindsight-api-slim + Node/control plane
├── apparmor.txt         # AppArmor profile
└── rootfs/
    └── etc/
        ├── cont-init.d/
        │   ├── 20-postgres.sh   # cluster init, database, pgvector
        │   └── 30-config.sh     # options -> HINDSIGHT_API_* env
        └── services.d/
            ├── hindsight/
            │   ├── run          # PostgreSQL + hindsight-api
            │   └── finish       # clean PostgreSQL shutdown
            └── control-plane/
                └── run          # Next.js web UI (optional, menu-selectable)
```

## License

MIT

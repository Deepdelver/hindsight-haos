# Hindsight HAOS

Home Assistant OS addon for [Hindsight](https://hindsight.vectorize.io/) — persistent AI agent memory with retain, recall, and reflect APIs.

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

## Configuration

| Option | Default | Purpose |
| --- | --- | --- |
| `llm_provider` | `llamacpp` | LLM provider. `llamacpp` runs a small local model inside the addon — no key. Change to `openai`, `ollama`, `groq`, `anthropic`, ... for a different one |
| `llm_api_key` | — | Only needed for hosted providers |
| `llm_model` | `gemma-4-e2b-it` | Model name (default model for the chosen provider) |
| `llm_base_url` | — | Custom endpoint (Ollama, OpenAI-compatible proxies) |
| `embeddings_provider` | `onnx` | Local ONNX embeddings, no key. Hosted: `openai`, `cohere`, `tei`, ... |
| `embeddings_model` | `intfloat/multilingual-e5-small` | Embedding model |
| `reranker_provider` | `onnx` | Local ONNX reranker, no key. `rrf` needs no model at all |
| `reranker_model` | `hindsight-ai/hs-rerank-1` | Reranker model (optional) |
| `llamacpp_model_path` | — | Optional GGUF path; otherwise auto-downloaded to `/data/hindsight-home/.hindsight/models` |
| `llamacpp_context_size` | `16384` | Local LLM context window |
| `llamacpp_gpu_layers` | `0` | GPU layers (`0` = CPU, `-1` = all) |
| `mcp_enabled` | `true` | Expose the MCP server |
| `control_plane` | `true` | Run the web UI (port 9999) |
| `control_plane_port` | `9999` | Port for the web UI |
| `worker_id` | `hindsight-haos` | Stable worker identity |
| `log_level` | `info` | Log verbosity |

An **env_vars** list is available for any additional `HINDSIGHT_API_*` variable.

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

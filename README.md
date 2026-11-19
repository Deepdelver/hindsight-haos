# Hindsight HAOS

Home Assistant OS addon for [Hindsight](https://hindsight.vectorize.io/) — persistent AI agent memory with retain, recall, and reflect APIs.

## Installation

1. In Home Assistant, go to **Settings** > **Apps** > **⋮** (top right) > **Repositories**
2. Add this repository URL: `https://github.com/Deepdelver/hindsight-haos`
3. Click **Install app** and find **Hindsight** in the list
4. Configure your LLM provider and API key
5. Start the addon

The first install builds the container on your Home Assistant (it installs PostgreSQL 15, pgvector, and the Hindsight API into a Python venv), so allow a few minutes.

## What is Hindsight?

Hindsight gives your AI agents persistent memory that works across all your tools — Hermes Agent, OpenClaw, OpenCode, Cursor, Claude Code, and any MCP-compatible client. Store context in one agent, retrieve it in another.

- **API Server**: Port 8888 (REST + MCP)
- **Control Plane**: Port 9999 (Web UI)
- **MCP endpoint**: `http://<your-ha-ip>:8888/mcp/<bank_id>/`

## Configuration

| Option | Default | Purpose |
| --- | --- | --- |
| `llm_provider` | `openai` | LLM provider |
| `llm_api_key` | — | API key (required unless Ollama) |
| `llm_model` | `gpt-4o-mini` | Model name |
| `llm_base_url` | — | Custom endpoint (Ollama, proxies) |
| `embeddings_provider` | `openai` | Embedding backend |
| `embeddings_model` | `text-embedding-3-small` | Embedding model |
| `reranker_provider` | `rrf` | Reranker (`rrf` needs no model) |
| `mcp_enabled` | `true` | Expose the MCP server |
| `control_plane` | `true` | Run the web UI (port 9999) |
| `control_plane_port` | `9999` | Port for the web UI |
| `worker_id` | `hindsight-haos` | Stable worker identity |
| `log_level` | `info` | Log verbosity |

An **env_vars** list is available for any additional `HINDSIGHT_API_*` variable.

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

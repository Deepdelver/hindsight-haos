# Hindsight AI Memory for Home Assistant OS

Hindsight is a persistent AI memory engine that gives your AI agents long-term memory with **retain**, **recall**, and **reflect** APIs. It runs as a standalone service on your Home Assistant, accessible to all your AI agents via MCP (Model Context Protocol).

## What it does

- **Retain** — Store facts, preferences, and context from conversations
- **Recall** — Retrieve relevant memories using semantic search
- **Reflect** — Synthesize insights from accumulated memories

## Setup

1. Install this addon
2. Go to **Configuration** and set:
   - **llm_provider** — `openai`, `anthropic`, `gemini`, `groq`, `deepseek`, `ollama`, `fireworks`, `openrouter`, `nous`, `custom`
   - **llm_api_key** — API key for the chosen provider (not needed for `ollama`)
   - **llm_model** — Model name (default `gpt-4o-mini`)
   - **llm_base_url** — Custom endpoint (optional; used for Ollama or a proxy)
   - **embeddings_provider** — `openai`, `ollama`, `cohere`
   - **embeddings_model** — Embedding model (default `text-embedding-3-small`)
   - **embeddings_api_key** — Separate key for embeddings (falls back to `llm_api_key`)
   - **reranker_provider** — `rrf` (no model needed), `cohere`, `flashrank`
   - **mcp_enabled** — `true`/`false`, expose the MCP server
   - **control_plane** — `true`/`false`, run the web UI on port 9999
   - **control_plane_port** — port for the web UI (default `9999`)
   - **worker_id** — Stable identity across restarts (default `hindsight-haos`)
   - **log_level** — `debug`, `info`, `warning`, `error`
3. Start the addon

## Configuration options

Every option is also exported as an environment variable, and the **env_vars** list
lets you set any additional variable directly:

| Option | Environment variable |
| --- | --- |
| `llm_provider` | `HINDSIGHT_API_LLM_PROVIDER` |
| `llm_api_key` | `HINDSIGHT_API_LLM_API_KEY` |
| `llm_model` | `HINDSIGHT_API_LLM_MODEL` |
| `llm_base_url` | `HINDSIGHT_API_LLM_BASE_URL` |
| `embeddings_provider` | `HINDSIGHT_API_EMBEDDINGS_PROVIDER` |
| `embeddings_model` | `HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL` |
| `reranker_provider` | `HINDSIGHT_API_RERANKER_PROVIDER` |
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

## Connecting your AI agents

Once running, Hindsight exposes an MCP server at:

```
http://<your-home-assistant-ip>:8888/mcp/<bank_id>/
```

### Hermes Agent

```bash
hermes config set mcp_servers.hindsight.url "http://<ha-ip>:8888/mcp/default/"
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

## Ports

- **8888** — Hindsight API and MCP server
- **9999** — Control Plane web UI

## Data

PostgreSQL data lives in `/data` inside the addon container and is included in
Home Assistant backups. The addon uses a cold backup, so Home Assistant stops it
while the backup runs.

## Using with Ollama

If you run the Ollama addon on the same Home Assistant:

- **llm_provider**: `ollama`
- **llm_api_key**: leave empty
- **llm_model**: your model, e.g. `qwen3.5:latest`
- **llm_base_url**: `http://homeassistant.local:11434`
- **embeddings_provider**: `ollama`

## Troubleshooting

- **Addon does not appear in the store** — the Supervisor silently drops apps whose
  `config.yaml` fails validation. Check **Settings > System > Logs > Supervisor**
  for a line starting `Can't read .../config.yaml`.
- **Container exits at start** — check the addon log. The most common cause is an
  empty `llm_api_key` with a provider that requires one.
- **MCP endpoint refuses connections** — confirm port 8888 is published and that
  `mcp_enabled` is `true`.

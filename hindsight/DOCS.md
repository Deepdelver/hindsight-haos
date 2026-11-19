# Hindsight AI Memory for Home Assistant OS

Hindsight is a persistent AI memory engine that gives your AI agents long-term memory with **retain**, **recall**, and **reflect** APIs. It runs as a standalone service on your Home Assistant, accessible to all your AI agents via MCP (Model Context Protocol).

## What it does

- **Retain** — Store facts, preferences, and context from conversations
- **Recall** — Retrieve relevant memories using semantic search
- **Reflect** — Synthesize insights from accumulated memories

## Setup

1. Install this addon
2. Go to **Configuration** and set:
   - **LLM Provider**: Your LLM provider (openai, groq, anthropic, ollama, custom)
   - **LLM API Key**: Your API key for the chosen provider
   - **LLM Model**: The model to use (default: gpt-4o-mini)
   - **Worker ID**: A stable identifier for this instance (default: hindsight-haos)
3. Start the addon

## Connecting your AI agents

Once running, Hindsight exposes an MCP server at:

```
http://<your-home-assistant-ip>:8888/mcp
```

### Hermes Agent

```bash
hermes config set mcp_servers.hindsight.url "http://<ha-ip>:8888/mcp"
```

### OpenClaw / Claude Code

```bash
claude mcp add --transport http hindsight http://<ha-ip>:8888/mcp
```

### OpenCode / Cursor / Any MCP client

Add to your MCP config:
```json
{
  "mcpServers": {
    "hindsight": {
      "url": "http://<ha-ip>:8888/mcp"
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

- **8888**: Hindsight API & MCP Server
- **9999**: Control Plane Web UI

## Data

All data is stored in `/data` inside the addon container and is included in Home Assistant backups. The addon uses PostgreSQL for storage.

## Using with Ollama

If you have the Ollama addon running on Home Assistant, set:
- **LLM Provider**: `ollama`
- **LLM API Key**: (leave empty or set any value)
- **LLM Model**: `qwen3.5:latest` (or your preferred model)

Then set the Ollama base URL via the addon's environment. The Ollama addon is typically reachable at `http://homeassistant.local:11434`.

# Hindsight HAOS

Home Assistant OS addon for [Hindsight](https://hindsight.vectorize.io/) — persistent AI agent memory with retain, recall, and reflect APIs.

## Installation

1. In Home Assistant, go to **Settings** > **Apps** > **⋮** (top right) > **Repositories**
2. Add this repository URL: `https://github.com/Deepdelver/hindsight-haos`
3. Click **Install app** and find **Hindsight** in the list
4. Configure your LLM provider and API key
5. Start the addon

## What is Hindsight?

Hindsight gives your AI agents persistent memory that works across all your tools — Hermes Agent, OpenClaw, OpenCode, Cursor, Claude Code, and any MCP-compatible client. Store context in one agent, retrieve it in another.

- **API Server**: Port 8888 (REST + MCP)
- **Control Plane**: Port 9999 (Web UI)
- **MCP endpoint**: `http://<your-ha-ip>:8888/mcp`

## License

MIT

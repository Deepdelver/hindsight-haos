# Hindsight HAOS

Home Assistant OS add-on for [Hindsight](https://hindsight.vectorize.io/) — persistent AI agent memory with a REST API, an MCP endpoint and a web UI. It gives every agent on your network the same long-term memory: store context in one tool, retrieve it in another.

Created and maintained by [Deepdelver](https://github.com/Deepdelver). This is an unofficial add-on; Hindsight itself lives at [hindsight.vectorize.io](https://hindsight.vectorize.io/) and [github.com/vectorize-io/hindsight](https://github.com/vectorize-io/hindsight).

## Features

**Memory engine (port 8888)**

- **Retain** — store facts, preferences and context from conversations, synchronously or asynchronously.
- **Recall** — hybrid retrieval: semantic/vector search, keyword/BM25 and graph expansion, combined and reranked.
- **Reflect** — an agentic loop that gathers evidence and answers through the lens of a bank's disposition, mission and directives.
- **Knowledge graph** — entities with temporal, semantic, entity and causal links; observations are consolidated from accumulated facts.
- **Banks** — isolated memories per agent, user or project; aliases, per-bank configuration and bank templates.
- **Documents** — retain files and text, split into passages, tagged, reprocessed and searched alongside memories.
- **Mental models and pages** — curated, refreshable summaries derived from a bank's memories, with staleness tracking.
- **Operations and diagnostics** — operation queue with progress, LLM request tracing, webhooks and an audit log (availability depends on the API version).
- **MCP server** — `http://<host>:8888/mcp/<bank_id>/` for MCP-compatible clients.

**Control Plane (port 9999, or via the HA sidebar)**

- Browse and manage banks, memories, documents, entities, observations and mental models.
- Run recall/reflect directly, trigger consolidation and inspect the graph.
- Configure disposition, mission, directives, consolidation strategies and webhooks per bank.
- Watch operations, LLM requests and system health.

**Local by default**

With `mode: simple` everything runs inside the add-on: a small llama.cpp LLM plus local ONNX embeddings and reranking. No API key, no external model server, no data leaving your machine. `mode: expert` lets you use hosted providers, Ollama or your own models.

## Installation

1. In Home Assistant go to **Settings → Apps → ⋮ (top right) → Repositories**.
2. Add `https://github.com/Deepdelver/hindsight-haos`.
3. Install **Hindsight** and start it.
4. On first start it downloads the local models (~3.5 GB) and builds the image; allow a few minutes.

The sidebar panel **Hindsight** opens the Control Plane through Home Assistant ingress. Direct access is also available on port 9999.

## Ports

| Port | Purpose |
| --- | --- |
| 8888 | REST API, MCP server, `/health` (watchdog) |
| 9999 | Control Plane for direct/LAN access (no path rewriting) |
| 9997 | Internal ingress port used by the Home Assistant sidebar |

Home Assistant proxies the sidebar panel at `https://<your-ha-host>/api/hassio_ingress/.../`. No port forwarding is needed for the UI.

## Configuration

| Option | Default | Purpose |
| --- | --- | --- |
| `mode` | `simple` | `simple` = local models, nothing to configure. `expert` = choose providers/models yourself |
| `llm_provider` | `llamacpp` | LLM provider; `llamacpp` is local and free. Hosted: `openai`, `ollama`, `groq`, `anthropic`, `gemini`, `openrouter`, `nous`, ... Since 1.2.24 the legacy `custom` choice is mapped to `openai` and requires `llm_base_url` |
| `llm_api_key` | — | Needed only for hosted providers |
| `llm_model` | `gemma-4-e2b-it` | Model name for the selected provider |
| `llm_base_url` | `""` (empty) | Custom endpoint for Ollama / an OpenAI-compatible proxy; expert mode only (empty = provider default) |
| `embeddings_provider` | `onnx` | Local ONNX embeddings by default |
| `embeddings_model` | `auto` | Let Hindsight pick and download its default; set an id to pin |
| `reranker_provider` | `onnx` | Local ONNX reranker; `rrf` needs no model |
| `reranker_model` | `auto` | Let Hindsight pick its default; set an id to pin |
| `llamacpp_model_path` | — | Optional GGUF path (otherwise auto-downloaded to `/data/hindsight-home/.hindsight/models`) |
| `llamacpp_context_size` | `16384` | Local LLM context window |
| `llamacpp_gpu_layers` | `0` | `0` = CPU, `-1` = all layers |
| `mcp_enabled` | `true` | Expose the MCP server |
| `control_plane` | `true` | Run the web UI |
| `control_plane_port` | `9999` | Direct UI port |
| `worker_id` | `hindsight-haos` | Stable worker identity across restarts |
| `log_level` | `info` | `debug`, `info`, `warning`, `error` |
| `env_vars` | `[]` | Any extra `HINDSIGHT_API_*` variable as `{name, value}` |

In `simple` mode the provider, model and base-URL fields are ignored; the local stack is always used. In `expert` mode they are passed through. `env_vars` works in both modes. A full option-to-environment-variable map and provider-specific notes are in [hindsight/DOCS.md](hindsight/DOCS.md).

## Connecting agents

### Hermes Agent (recommended)

Hindsight ships as a Hermes memory-provider plugin in the official catalog. No API key is needed for the add-on:

```bash
hermes plugins install hindsight --enable --yes-deps
hermes config set memory.provider hindsight
hermes memory status                  # Provider: hindsight, Status: available
```

Create `$HERMES_HOME/hindsight/config.json` (for the default profile `~/.hermes/hindsight/config.json`):

```json
{
  "mode": "local_external",
  "api_url": "http://9b734b76-hindsight:8888",
  "bank_id": "hermes",
  "recall_min_scores": { "reranker": 0.25 }
}
```

Use the add-on's own hostname from **Settings → Apps → Hindsight → Hostname** (the prefix is unique per installation); from another machine use `http://<ha-ip>:8888`. Restart a running gateway with `hermes gateway restart` after changing the config. The `hermes` bank appears in the Control Plane after the first retain. `recall_min_scores.reranker` filters off-topic hits on a small bank.

Full reference: https://hindsight.vectorize.io/sdks/integrations/hermes

### MCP clients

```bash
# Claude Code
claude mcp add --transport http hindsight http://<ha-ip>:8888/mcp/default/
```

```json
{
  "mcpServers": {
    "hindsight": { "url": "http://<ha-ip>:8888/mcp/default/" }
  }
}
```

Use your bank id in place of `default`. An MCP entry is for clients that do not use the Hermes memory provider — do not configure both for the same client.

## Stability

This add-on is built to behave like a normal Home Assistant add-on: a pinned, reproducible image, health-checked startup, ingress that follows HA conventions, and regression tests for the parts that have broken before.

- **Pinned versions.** The Dockerfile pins the Control Plane npm package
  (`@vectorize-io/hindsight-control-plane`) to a specific release. The matching
  API version validated for that release is recorded in
  `hindsight/versions.json`; the API is installed from PyPI at build time at that
  same pinned version. API and UI versions must match; a mismatch produces UI
  404s and empty memory tabs. Both are bumped together in one release.
- **Automatic version watch.** A daily cron job runs
  `scripts/check_versions.py --create-task`. It compares the recorded/pinned
  versions with npm and PyPI and, on drift, opens one idempotent Kanban task.
  Nothing changes at runtime: the normal assessment, tests and release flow
  decide whether to bump the pins and publish a new add-on version.
- **Add-on auto-update.** Home Assistant updates the add-on automatically when
  a new version is published, without allowing unpinned upstream code into a
  running container.
- **Ingress-safe paths.** The UI receives its base path at runtime through `NEXT_PUBLIC_BASE_PATH`, so API calls are prefixed exactly once. Only the two genuine navigation URL builders are rewritten in JavaScript; API path suffixes are left alone and the bank-selector regex accepts the ingress prefix.
- **Regression tests.** `python3 hindsight/tests/test_ingress_rewrite.py` checks the nginx template for all of the above. Run it before building or changing the template.
- **No stale assets.** The ingress server sends `Cache-Control: no-store` so an update cannot leave old UI assets in the browser.
- **Watchdog.** `http://[HOST]:[PORT:8888]/health` restarts the add-on if the API stops answering.
- **Backups.** PostgreSQL data lives in `/data` and is included in Home Assistant backups (`backup: cold` — the add-on is stopped during backup).
- **Release discipline.** Every change that must reach installed users bumps `version` in `hindsight/config.yaml`; Supervisor only offers an update for a new version. After pushing, reload the store (`POST /addons/reload`) and update the add-on, then verify both the direct port and the sidebar panel.

## Development and testing

Before **any push to GitHub**, the agent assessment pipeline on the project's
Kanban board must run for the change set being pushed. Two layers enforce it:

- **Locally:** a pre-push hook. Run `scripts/setup-hooks.sh global` once — it
  writes a dispatcher to `~/.hermes/git-hooks` and sets `core.hooksPath`
  globally. The dispatcher only gates repositories whose origin URL contains
  `hindsight-haos`, so other repos are unaffected. `scripts/setup-hooks.sh
  local` sets the hook for the current clone only.
- **On GitHub:** branch protection on `main` requires a pull request and the
  `regression` status check from `.github/workflows/regression-tests.yml`.
  `--no-verify` can skip the local hook but cannot bypass the server-side rule.

```bash
cd hindsight-haos
python3 hindsight/tests/test_source_defaults.py   # source config defaults / no credentials
python3 hindsight/tests/test_ingress_rewrite.py   # ingress rewrite regression tests
python3 hindsight/tests/test_prepush_pipeline.py  # pre-push gate regression tests
python3 hindsight/tests/test_version_watch.py     # upstream version watch
python3 scripts/check_versions.py                 # live comparison (no changes)
```

The flow is:

1. `git push` triggers the pre-push hook (the global dispatcher installed by
   `scripts/setup-hooks.sh global`, or `.githooks/pre-push` in a local-only
   setup), which creates a task on the `hindsight-haos` Kanban board keyed to
   the change set — the first unpushed commit without a `Pipeline-Key:` trailer
   (the current HEAD is recorded in the task body for context). The push is
   aborted at this point.
2. The agent assesses the diff, updates `README.md` / `hindsight/DOCS.md` where
   behaviour, ports, options or troubleshooting changed, and adds or updates
   tests in `hindsight/tests/`. It runs all five regression suites (source
   defaults, ingress, pre-push gate, version watch and cont-init provider
   mapping) and reports.
3. Re-run `git push`. The hook sees the completed task, runs all five regression
   suites itself and allows the push only if they pass.

A new change set starts with any commit that lacks a `Pipeline-Key:` trailer;
its SHA becomes the task key. Commits produced by the assessment carry that
trailer, so they do not restart the gate — no manual id to bump. The task's
body contains the exact checklist; the script is `scripts/pre-push-pipeline.sh`.

The test reads the real `rootfs/etc/nginx.conf.template`, parses its `sub_filter` rules and applies
them to representative HTML/JS. It fails if an API suffix gets the ingress base
injected, if a navigation builder loses it, or if the bank-selector regex is no
longer ingress-aware. Set `HINDSIGHT_NGINX_TEMPLATE` to test a different template
revision. `test_source_defaults.py` keeps `config.yaml` credential-free and
checks the local `simple` / `llamacpp` defaults, the empty `llm_base_url` and
its non-optional `str` schema. `test_prepush_pipeline.py` checks the hook/script
wiring, that the GitHub workflow runs the same suites as the hook, and the
gate's decision logic (done / none / running, test failure) with fake
`git` and `hermes` binaries; it does not touch the real board.
`test_version_watch.py` loads `scripts/check_versions.py` with a stubbed
Dockerfile, `versions.json` and network calls, so it checks pin parsing, drift
detection, the idempotent task key and the CLI exit codes offline.

If a push is blocked, look for the task keyed to the first unpushed commit
without a `Pipeline-Key:` trailer (the key and HEAD are printed by the hook):
its status must be `done`, and all five regression suites must pass.

## Troubleshooting

- **Add-on does not appear in the store** — Supervisor drops add-ons whose `config.yaml` fails validation. Check **Settings → System → Logs → Supervisor** for `Can't read .../config.yaml`.
- **Container exits at start** — check the add-on log. A common cause is an empty `llm_api_key` with a provider that requires one.
- **Add-on crash-loops with `Invalid LLM provider: custom`** — fixed in 1.2.24: `custom` is mapped to `openai` (and requires `llm_base_url`). Update the add-on. On older versions, choose `openai` and set `llm_base_url` to your OpenAI-compatible gateway; keep `embeddings_provider: onnx`.
- **`Client Error / HTTP 404` in the UI** — check that the Control Plane version matches the API version and that the ingress template passes the regression test; then do a hard refresh to discard cached assets.
- **Cannot select a bank in the sidebar UI** — the bank-selector regex rewrite is missing from the nginx template; run the regression test.
- **Retains keep retrying / `429 Too Many Requests` in the addon log** — a free hosted model is rate-limiting fact extraction. This is an upstream provider limit, not an add-on fault: switch `mode` to `simple` (local models) or use a provider key with a higher quota. Retains are retried by the worker, so memories are not lost.
- **MCP endpoint refuses connections** — confirm port 8888 is published and `mcp_enabled` is `true`.

## License

MIT

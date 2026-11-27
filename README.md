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
| `consolidation_llm_provider` | `""` (empty) | Expert only: separate provider for observation consolidation; empty = reuse `llm_provider` |
| `consolidation_llm_model` | `""` (empty) | Expert only: separate model for consolidation; empty = reuse `llm_model` |
| `consolidation_llm_base_url` | `""` (empty) | Expert only: separate endpoint for consolidation; empty = reuse `llm_base_url` |
| `consolidation_llm_api_key` | `""` (empty) | Expert only: API key for the consolidation provider; empty = reuse `llm_api_key` |
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

### Dedicated consolidation LLM (expert mode, since 1.2.26)

Consolidation — turning retained facts into Observations — uses the retain LLM by
default. That coupling hurts when the backlog grows: retain wants strong
structured output, while consolidation gets a much larger prompt and mostly wants
a fast, cheap route. In `expert` mode you can override any of the four
`consolidation_llm_*` options above to route only that work elsewhere. They map to
`HINDSIGHT_API_CONSOLIDATION_LLM_PROVIDER`, `..._MODEL`, `..._BASE_URL` and
`..._API_KEY`. **Every option you leave empty falls back to the corresponding
normal LLM setting**, so partial overrides are valid.

Example — keep extraction on a quality alias, send consolidation through a
separate gateway route:

```yaml
mode: expert
llm_provider: openai
llm_base_url: http://<host>:20128/api/v1
llm_api_key: <gateway-key>
llm_model: combo
consolidation_llm_provider: openai
consolidation_llm_base_url: http://<host>:20128/api/v1
consolidation_llm_api_key: <gateway-key>
consolidation_llm_model: <consolidation-model>
```

All four defaults are empty in the shipped config, so nothing new is written to
the runtime env file and today's behaviour is unchanged. `simple` mode ignores
these options even if a value was stored during an earlier expert setup; a
local-only install cannot start calling out by accident.

This is an operational **throughput** fix for the pending-consolidation backlog.
It does not improve recall, repair a failed retain, or delete the backlog. Those
still require a healthy extraction route and, where needed, a retry of failed
operations. Measure a candidate on the real consolidation prompt before
switching: on this host `combo` and `grok-4.7` both exceeded 240 s on the 52,758
character prompt, `auto/best-free` timed out at 150 s during extraction, and
`google/gemini-2.5-flash-lite` returned 401 because no credentials were
configured — so no measured model can honestly be called fast for consolidation
yet. Bound the prompt with the per-bank limits below first.

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

- **Pinned versions.** The Dockerfile pins both upstream components to **1.3.0**:
  `hindsight-api-slim[local-llm,local-onnx]` from PyPI and
  `@vectorize-io/hindsight-control-plane` from npm. Both 1.3.0 packages were
  published on 2026-11-24 from the same upstream `Release v1.3.0` commit; the
  pair is recorded in `hindsight/versions.json`. API and UI versions must match;
  a mismatch produces UI 404s and empty memory tabs. Both were bumped together in
  add-on release 1.2.25 and remain pinned at 1.3.0 in 1.2.26. No config key was
  removed or renamed in 1.3.0,
  but the API ships migration work and enables knowledge banks by default: wait
  for `/health` on the first start after upgrading.
- **Automatic version watch.** A daily cron job runs
  `scripts/check_versions.py --create-task`. It compares the recorded/pinned
  versions with npm and PyPI and, on drift, opens one idempotent Zero Factory
  task on the `deepdelver-hindsight-haos` board (dedup key
  `version-watch-<api>-<cp>`). Nothing changes at runtime: the normal
  assessment, tests and release flow decide whether to bump the pins and publish
  a new add-on version.
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
python3 hindsight/tests/test_continit_providers.py # provider mapping / crash-loop guard
python3 hindsight/tests/test_setup_gh_issues.py   # GitHub issue templates + labels
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
   tests in `hindsight/tests/`. It runs all six regression suites (source
   defaults, ingress, pre-push gate, version watch, cont-init provider mapping
   and GitHub issue setup) and reports.
3. Re-run `git push`. The hook sees the completed task, runs all six regression
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
its status must be `done`, and all six regression suites must pass.

## GitHub issues and Zero Factory triage

Bug reports and feature proposals use the YAML forms in
`.github/ISSUE_TEMPLATE/`. Both forms apply the `zerofactory` label, which is
the explicit human signal for Zero Factory to open a human-gated Triage task;
blank issues are disabled and questions are directed to GitHub Discussions.
`python3 scripts/setup_gh_issues.py --path . --align` regenerates the
repo-aware `config.yml`, preserves customized forms that already carry the
label, and provisions the standard labels (`zerofactory`, `ai-investigate`,
`bug`, `feature`, `p0`–`p3`) via the GitHub CLI when authenticated.

## Troubleshooting

- **Add-on does not appear in the store** — Supervisor drops add-ons whose `config.yaml` fails validation. Check **Settings → System → Logs → Supervisor** for `Can't read .../config.yaml`.
- **Container exits at start** — check the add-on log. A common cause is an empty `llm_api_key` with a provider that requires one.
- **Custom cont-init script fails with `bashio::…: command not found` in a standalone container** — `bashio-standalone.sh` only implements the helpers this add-on and the four downloaded Home Assistant templates use (logging, `supervisor.ping`, `config`, `app.*`, `info.*`, `var.true`, `exit.*`, `api.supervisor`); helpers such as `config.array`, `services.*`, `net.wait_for`, the cache and the jq wrapper are not provided. Under Home Assistant Supervisor the full bashio library is available; in a standalone container rewrite custom helpers in plain shell/`jq` or run that script under Supervisor.
- **Add-on crash-loops with `Invalid LLM provider: custom`** — fixed in 1.2.24: `custom` is mapped to `openai` (and requires `llm_base_url`). Update the add-on. On older versions, choose `openai` and set `llm_base_url` to your OpenAI-compatible gateway; keep `embeddings_provider: onnx`.
- **`Client Error / HTTP 404` in the UI** — check that the Control Plane version matches the API version and that the ingress template passes the regression test; then do a hard refresh to discard cached assets.
- **Cannot select a bank in the sidebar UI** — the bank-selector regex rewrite is missing from the nginx template; run the regression test.
- **Retains keep retrying / `429 Too Many Requests` in the addon log** — a free hosted model is rate-limiting fact extraction. This is an upstream provider limit, not an add-on fault: switch `mode` to `simple` (local models) or use a provider key with a higher quota. Retains are retried by the worker, so memories are not lost.
- **MCP endpoint refuses connections** — confirm port 8888 is published and `mcp_enabled` is `true`.

### Growing Observations / Pending count (consolidation backlog)

If the **Observations** tab keeps climbing and a bank has hundreds or thousands of
`consolidation_state=pending` memories, the LLM extractor is falling behind. This is
almost always a routing problem, not an add-on bug. On 2026-11-26 bank `hermes`
reached 1566 pending memories: the `auto/best-fast` alias on OmniRoute failed over
through dead providers (502/404/400, 60–115 s per call) and consolidation on
14k-token prompts took 110–327 s, so the worker could not drain the queue.

Since 1.2.26, expert installs can send just the consolidation calls to a
separate route with the four `consolidation_llm_*` options described in
[Dedicated consolidation LLM](#dedicated-consolidation-llm-expert-mode-since-1226).
They are empty by default, so the upgrade itself changes no routing. This is a
throughput lever, not a recall fix: always confirm the extraction route is
healthy first.

Diagnose in this order (replace `<bank>` with the bank id, e.g. `hermes`):

1. Count the backlog and check how old it is:
   `GET /v1/default/banks/<bank>/memories/list?consolidation_state=pending&limit=1`
   (read `total`; `GET /v1/default/banks/<bank>/stats` also reports
   `pending_consolidation` and `failed_consolidation`).
2. See whether consolidation work is queued, running or retrying, and how far it got:
   `GET /v1/default/banks/<bank>/operations?type=consolidation&limit=20`
   (check `status`, `error_message`, `retry_count` and `progress.total`).
3. Inspect the LLM calls behind those operations:
   `GET /v1/default/banks/<bank>/llm-requests?limit=20`
   (check `provider`, `model`, `status`, `duration_ms` and the timestamps).

**Dead extraction route vs. the old OmniRoute heap-503.** A dead route keeps the
gateway and `/health` green, but `llm-requests` shows scattered provider
`502/404/400` statuses — often several providers in sequence — with slow traces
(tens of seconds up to ~5 minutes). The earlier OmniRoute heap-503 was a
gateway-level failure: the proxy returned `503` for every route at once and its own
log showed heap/OOM pressure. Inspect `llm-requests` before changing anything;
a gateway-level 503 must be fixed at the gateway first.

Safe runtime mitigations (per-install, no add-on rebuild and no source change):

- Point extraction at a working route through the add-on **env_vars**, for example
  `{name: HINDSIGHT_API_LLM_MODEL, value: combo}` (plus the matching gateway base
  URL/key if applicable). Leave the source `config.yaml` on `mode: simple`,
  `llm_provider: llamacpp` with empty `llm_api_key` / `llm_base_url` — routing
  overrides belong in the installed options, never in the repository.
- Tighten the per-bank consolidation limits so each call fits the model context.
  Use the bank-config PATCH with the required `updates` wrapper (adjust the numbers
  to your model):

  ```bash
  curl -X PATCH 'http://<ha-ip>:8888/v1/default/banks/<bank>' \
    -H 'Content-Type: application/json' \
    -d '{"updates":{
          "consolidation_max_memories_per_round": 10,
          "consolidation_llm_parallelism": 2,
          "consolidation_source_facts_max_tokens": 4000
        }}'
  ```

Then watch `pending_consolidation` fall while `total_observations` rises. **Do not
delete pending memories to clear the backlog**: observations are regenerated by
consolidation from those memories, so deleting them permanently loses the derived
knowledge. Once the route is healthy, failed operations can be retried from the
Operations screen (`POST .../operations/{id}/retry`).

## License

MIT

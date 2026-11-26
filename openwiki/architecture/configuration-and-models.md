---
type: concept
title: Configuration and model provider selection
description: How add-on options are converted into the HINDSIGHT_API_* environment file, how simple and expert modes differ, and how provider keys, model ids and env_vars overrides are validated.
tags: [configuration, models, providers, environment, add-on]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-25T23:47:00.311Z
sources:
  - id: openwiki-source-150ac6e3b9a2e0438493c07a
    resource: repo://hindsight/config.yaml
  - id: openwiki-source-09bac0922ebe4e19a399d3f7
    resource: repo://hindsight/DOCS.md
  - id: openwiki-source-d3e4484cf4bae0757db91352
    resource: repo://hindsight/rootfs/etc/cont-init.d/30-config.sh
  - id: openwiki-source-fcec0817d255962190de1380
    resource: repo://hindsight/rootfs/etc/services.d/hindsight/run
  - id: openwiki-source-9a137ea6cc4d11fbae840612
    resource: repo://hindsight/tests/test_continit_providers.py
  - id: openwiki-source-86617171982c41a2a92c0492
    resource: repo://hindsight/tests/test_source_defaults.py
generated: { by: "hermes", at: "2026-11-25T23:47:00.311Z" }
---

# Configuration and model provider selection

The Home Assistant Configuration tab exposes a small set of options, but the Hindsight API is configured through `HINDSIGHT_API_*` environment variables. The bridge between them is `hindsight/rootfs/etc/cont-init.d/30-config.sh`, which runs once during container initialization and writes `/data/hindsight/env`. The API service later sources that file (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L82-L85`, `repo://hindsight/rootfs/etc/services.d/hindsight/run#L17-L21`).

## Declared options and defaults

`hindsight/config.yaml` defines the Supervisor schema and defaults: `mode: simple`, `llm_provider: llamacpp`, `llm_api_key: ""`, `llm_model: gemma-4-e2b-it`, `llm_base_url: ""`, local `onnx` embeddings and reranker with `auto` models, `mcp_enabled: true`, `worker_id: hindsight-haos`, `log_level: info`, `control_plane: true` on port 9999, and an empty `env_vars` list (`repo://hindsight/config.yaml#L19-L45`). Credentials are declared as `password` schema entries, so values entered in the UI are per-install and never stored in the repository (`repo://hindsight/config.yaml#L46-L71`).

`test_source_defaults.py` enforces that contract on the checked-in file: the API key and base URL must be empty, mode must be `simple`, provider must be `llamacpp`, `llm_base_url` must exist as a non-optional `str`, no `sk-` token may appear, and `version` must be a quoted string (`repo://hindsight/tests/test_source_defaults.py#L40-L70`).

## Simple versus expert mode

`30-config.sh` reads each option with a default, then checks the mode. If the mode is anything other than `expert`, it overwrites the LLM, embeddings and reranker choices with the local stack: `llamacpp` / `gemma-4-e2b-it`, `onnx` embeddings, `onnx` reranker, all model ids reset to `auto`, empty base URL and key, context 16384 and 0 GPU layers. This makes the default install work with no API key and no data leaving the machine (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L13-L51`).

In `expert` mode the selected providers, models, key, base URL and llama.cpp settings are passed through. `env_vars` still applies in both modes (`repo://hindsight/DOCS.md#L66-L75`).

## Emitted variables

The generated env file always includes the database URL `postgresql://postgres@127.0.0.1:5432/hindsight`, provider/model settings, `HINDSIGHT_API_MCP_ENABLED`, `HINDSIGHT_API_WORKER_ID`, host/port `0.0.0.0:8888` and the log level (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L86-L96`). Optional lines are emitted only when relevant:

- the API key line when a key is present, or the fixed placeholder `local` when the raw provider was `custom` and the mapped provider is `openai` (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L98-L105`);
- the base URL and MCP auth token when set (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L106-L111`);
- a provider-specific model id only when the user pinned one — `auto` emits no id so Hindsight can use and update its own provider default (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L113-L146`);
- for `llamacpp`, GPU layers, context size, optional GGUF path, a bounded retain completion budget of 8192 tokens and a concurrency limit of 2 (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L148-L157`).

The option-to-environment table in `hindsight/DOCS.md` documents the same mapping for users, including the `embeddings_api_key` fallback to `llm_api_key` for the OpenAI embeddings provider (`repo://hindsight/DOCS.md#L41-L57`, `repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L127-L132`).

## Validation and the legacy `custom` provider

The Hindsight API rejects `llm_provider: custom`, so the add-on keeps the user's raw choice for validation but maps `custom` to `openai`, which speaks the OpenAI wire format used by gateways such as OmniRoute and LiteLLM. A `custom` choice without `llm_base_url` is fatal with a startup log message naming the missing option. Local providers (`llamacpp`, `ollama`, `lmstudio`, plus raw `custom`) are allowed without a key; every other provider requires `llm_api_key` unless simple mode already forced the local stack (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L53-L80`).

`env_vars` entries are read as JSON objects with `name` and `value` or as `KEY=VALUE` strings, and only keys beginning with `HINDSIGHT_API_` are emitted. An `env_vars` attempt to set `HINDSIGHT_API_LLM_PROVIDER` is ignored with a warning on stderr, because it could reintroduce `custom` or undo the mapping after all guards ran; the warning is deliberately not written into the env file. Since the API service sources the file, the last line wins for ordinary settings (`repo://hindsight/rootfs/etc/cont-init.d/30-config.sh#L159-L185`).

`test_continit_providers.py` executes the real cont-init script with a stubbed bashio in a temporary directory and asserts each of these paths: `custom` with a base URL maps to exactly one `openai` provider line plus the placeholder key, `custom` without a base URL exits with a clear error and no env file, simple mode with `custom` stays keyless on `llamacpp`, a real key is preserved, both object-form and `KEY=VALUE` provider overrides are ignored and warned about, expert `openai` without a key is blocked, and simple mode with a stored `openai` choice still boots locally (`repo://hindsight/tests/test_continit_providers.py#L92-L225`).

## Operational consequences

Because vector spaces are model-specific, changing an embeddings model after memories exist requires a reembed; `hindsight/DOCS.md` recommends `hindsight-admin reembed` and documents clearing ONNX query/passage prefixes when using `hindsight-ai/hs-embed-1` (`repo://hindsight/DOCS.md#L96-L108`). An empty key on a hosted provider or rate limiting on a free gateway blocks fact extraction, so retains fail while recall of existing memories continues (`repo://hindsight/DOCS.md#L230-L238`).

See [Add-on runtime and process topology](../architecture/addon-runtime.md) for where the env file is consumed, and [Regression suites and precommit gate](../workflows/testing-and-regressions.md) for how to run the provider tests.

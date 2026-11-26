---
type: "Reference"
title: "Hindsight HAOS quickstart"
openwiki_generated: true
verified:
  - by: openwiki/0.9.0
    at: 2026-11-25T23:47:00.311Z
sources:
  - id: openwiki-source-150ac6e3b9a2e0438493c07a
    resource: repo://hindsight/config.yaml
  - id: openwiki-source-0a3d7c05f6e1a163dada353c
    resource: repo://hindsight/rootfs/etc/services.d/control-plane/run
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "hermes", at: "2026-11-25T23:47:00.311Z" }
---


# Hindsight HAOS quickstart

This repository is an unofficial Home Assistant OS add-on that packages [Hindsight](https://hindsight.vectorize.io/) — a persistent memory engine with a REST API, an MCP endpoint and a web UI — so every agent on the network can share long-term memory (`repo://README.md#L1-L5`, `repo://repository.yaml#L1-L3`). It is a packaging and operations project: upstream API and Control Plane releases are pinned here, preceded by tests and gates, not developed in this repository.

## What it provides

The API on port 8888 exposes **retain** (store facts, preferences and context), **recall** (hybrid vector, keyword and graph retrieval with reranking), **reflect** (evidence-gathering answers through a bank's disposition, mission and directives), knowledge graphs, isolated banks, documents, mental models and an MCP server at `http://<host>:8888/mcp/<bank_id>/` (`repo://README.md#L7-L19`). The Control Plane on port 9999 (or the Home Assistant sidebar) browses banks and memories, runs recall/reflect, inspects the graph and shows operations and health (`repo://README.md#L21-L26`).

`mode: simple` is the default and uses a local llama.cpp LLM plus local ONNX embeddings and reranking — no key, no external model server and no data leaving the machine. `mode: expert` passes provider and model choices through for hosted APIs, Ollama or self-hosted models (`repo://README.md#L28-L30`, `repo://hindsight/config.yaml#L20-L36`).

## Install and first start

Add `https://github.com/Deepdelver/hindsight-haos` as a Home Assistant repository under **Settings → Apps → ⋮ → Repositories**, install **Hindsight** and start it. The first start downloads about 3.5 GB of local models and builds the image, so allow a few minutes (`repo://README.md#L32-L37`). The sidebar panel **Hindsight** opens the Control Plane through ingress; direct LAN access is on port 9999 (`repo://README.md#L39`).

## Ports and entry points

| Port | Entry point |
| --- | --- |
| 8888 | REST API, `/health` watchdog and MCP at `/mcp/<bank_id>/` |
| 9999 | Direct Control Plane UI (no path rewriting) |
| 9997 | Internal ingress port used by the Home Assistant sidebar |
| 9998 | Internal Next.js backend behind nginx, not for direct client use |

The port assignments are declared in `hindsight/config.yaml` and summarized in the README (`repo://hindsight/config.yaml#L10-L13`, `repo://hindsight/config.yaml#L40-L45`, `repo://README.md#L41-L49`, `repo://hindsight/rootfs/etc/services.d/control-plane/run#L14-L17`). For a non-Hermes MCP client, register `http://<ha-ip>:8888/mcp/default/` (replace `default` with the bank id); do not configure both a native Hermes memory provider entry and an MCP entry for the same client (`repo://README.md#L103-L118`). Use the add-on's own hostname from the Home Assistant UI for clients running inside the network (`repo://README.md#L99-L101`).

## Where to go next

| Question | Page |
| --- | --- |
| How does the image boot, where is state stored, how do services stop and restart? | [Add-on runtime and process topology](architecture/addon-runtime.md) |
| How do add-on options become `HINDSIGHT_API_*` variables, and how do provider modes and keys work? | [Configuration and model provider selection](architecture/configuration-and-models.md) |
| Why is the UI proxied on two ports, and how does ingress path rewriting work? | [Control plane and Home Assistant ingress](architecture/ingress-and-control-plane.md) |
| How are upstream versions pinned, watched and released? | [Version pinning, drift detection and release gates](workflows/release-and-version-watch.md) |
| Which tests protect the add-on, and how do precommit and CI run them? | [Regression suites and precommit gate](workflows/testing-and-regressions.md) |

Source code and tests remain authoritative; these pages are optimized for retrieval, not a replacement for the README's full option reference (`repo://README.md#L51-L60`).

---
type: workflow
title: Regression suites and precommit gate
description: Why each standalone Python regression suite exists, what invariant it protects, how precommit.sh runs format/build/test phases and how the same five suites run in the pre-push gate and CI.
tags: [testing, regressions, precommit, ruff, ci]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-25T23:47:00.311Z
sources:
  - id: openwiki-source-73b3d95aa018b1d5467bc96c
    resource: repo://.github/workflows/regression-tests.yml
  - id: openwiki-source-9ab161c6e9774cf771b19ced
    resource: repo://.zerofactory/precommit.sh
  - id: openwiki-source-9a137ea6cc4d11fbae840612
    resource: repo://hindsight/tests/test_continit_providers.py
  - id: openwiki-source-a922bbc1f93dc44cd6e3c69e
    resource: repo://hindsight/tests/test_ingress_rewrite.py
  - id: openwiki-source-7fd01caf0144fb80634d05e2
    resource: repo://hindsight/tests/test_prepush_pipeline.py
  - id: openwiki-source-86617171982c41a2a92c0492
    resource: repo://hindsight/tests/test_source_defaults.py
  - id: openwiki-source-a48e571198cab1ffcb8bd0d4
    resource: repo://hindsight/tests/test_version_watch.py
  - id: openwiki-source-d763dfe33a2468865a9b9ce5
    resource: repo://ruff.toml
  - id: openwiki-source-69c8fbb2b27ed8bbfd303378
    resource: repo://scripts/pre-push-pipeline.sh
generated: { by: "hermes", at: "2026-11-25T23:47:00.311Z" }
---

# Regression suites and precommit gate

This repository has no package build and no pytest stack. All verification lives in five standalone, standard-library-only Python scripts under `hindsight/tests/`, invoked directly by the Zero Factory precommit script, the pre-push gate and GitHub Actions. The release/assessment process that decides *when* these run is described in [Version pinning, drift detection and release gates](../workflows/release-and-version-watch.md).

## The five suites and their invariants

- `test_source_defaults.py` parses the checked-in `hindsight/config.yaml` and fails if a credential, a forced expert route, a wrong `llm_base_url` schema or an unquoted version appears. It keeps per-install routing out of the public repository (`repo://hindsight/tests/test_source_defaults.py#L2-L10`, `repo://hindsight/tests/test_source_defaults.py#L40-L70`).
- `test_ingress_rewrite.py` reads the real nginx template, extracts its `sub_filter` rules and applies them to HTML/JS fixtures. It protects the two historically broken behaviors: API suffixes must not receive the ingress prefix (HTTP 404) and the bank-selector regex must tolerate it (`repo://hindsight/tests/test_ingress_rewrite.py#L1-L13`, `repo://hindsight/tests/test_ingress_rewrite.py#L86-L140`); see [Control plane and Home Assistant ingress](../architecture/ingress-and-control-plane.md).
- `test_prepush_pipeline.py` exercises hook and dispatcher wiring, fail-closed behavior, change-set key derivation from multi-line commit bodies, board-status detection, an end-to-end fake git/hermes push and parity between the local gate and the CI workflow (`repo://hindsight/tests/test_prepush_pipeline.py#L1-L12`, `repo://hindsight/tests/test_prepush_pipeline.py#L251-L333`).
- `test_version_watch.py` stubs registry fetches and `subprocess.run` so drift detection, numeric tuple comparison, `.post1` handling, exit codes and the idempotent Kanban key are checked without network access (`repo://hindsight/tests/test_version_watch.py#L56-L103`, `repo://hindsight/tests/test_version_watch.py#L149-L183`).
- `test_continit_providers.py` executes the real `30-config.sh` with a stubbed bashio in a temp dir, covering the `custom` to `openai` mapping, the placeholder key, simple-mode override, missing-key guards and the `env_vars` provider-override warning (`repo://hindsight/tests/test_continit_providers.py#L1-L18`, `repo://hindsight/tests/test_continit_providers.py#L92-L225`); see [Configuration and model provider selection](../architecture/configuration-and-models.md).

Run any suite directly, for example `python3 hindsight/tests/test_ingress_rewrite.py`; no dependency installation or test runner is needed. The README's development section still describes four suites, but the gate, precommit and CI all run five — the provider suite was added later (`repo://README.md#L176-L181`, `repo://.zerofactory/precommit.sh#L33-L39`).

## Precommit phases

`.zerofactory/precommit.sh` accepts `format`, `build`, `test`, `install-hook` or `all` (the default) (`repo://.zerofactory/precommit.sh#L110-L121`):

1. **format** runs `ruff check --fix .` and `ruff format .`. If ruff is missing, the script installs the pinned `ruff==0.17.6` via `uv tool install` and falls back to `python3 -m pip install --user`, adding `~/.local/bin` to `PATH` so the executable is found (`repo://.zerofactory/precommit.sh#L30-L31`, `repo://.zerofactory/precommit.sh#L41-L63`). `ruff.toml` keeps the rule set deliberately conservative — `E4`, `E7`, `E9` and `F` at line length 100 for Python 3.12, with extra ignores for test files — so auto-fix cannot rewrite test intent (`repo://ruff.toml#L1-L14`).
2. **build** is `python3 -m compileall -q .`; there is no package manifest to build (`repo://.zerofactory/precommit.sh#L65-L68`).
3. **test** verifies the stdlib imports the suites rely on, then runs each of the five files in order and fails on a missing file (`repo://.zerofactory/precommit.sh#L70-L90`).

Because `install-hook` symlinks the script into the hooks directory, `BASH_SOURCE[0]` points at the hook rather than the repository when git invokes it. The script walks the symlink chain and re-derives `ROOT_DIR` from the real script path before `cd`, so all phases run from the repo root in both worktree and custom `core.hooksPath` layouts (`repo://.zerofactory/precommit.sh#L12-L28`, `repo://.zerofactory/precommit.sh#L92-L108`).

## Shared verification across gates

The same five suites are listed in precommit, in `scripts/pre-push-pipeline.sh` (after the assessment task reaches `done`) and as five steps in `.github/workflows/regression-tests.yml`, which runs on Python 3.12 for pushes and pull requests to `main` (`repo://.zerofactory/precommit.sh#L33-L39`, `repo://scripts/pre-push-pipeline.sh#L61-L70`, `repo://.github/workflows/regression-tests.yml#L1-L27`). `test_prepush_pipeline.py` asserts this parity so a suite cannot silently disappear from one of the three paths (`repo://hindsight/tests/test_prepush_pipeline.py#L9-L12`).

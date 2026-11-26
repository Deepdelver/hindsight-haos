---
type: workflow
title: Version pinning, drift detection and release gates
description: How matching Hindsight API and Control Plane versions are pinned and recorded, how the daily drift watch raises an idempotent Kanban task, and how the pre-push and GitHub gates enforce assessment before release.
tags: [releases, versioning, version-watch, kanban, pre-push]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-25T23:47:00.311Z
sources:
  - id: openwiki-source-73b3d95aa018b1d5467bc96c
    resource: repo://.github/workflows/regression-tests.yml
  - id: openwiki-source-10e42256adf0eb31d263190b
    resource: repo://hindsight/Dockerfile
  - id: openwiki-source-dc937830b80bdb633b7f5f89
    resource: repo://hindsight/versions.json
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-9a974e970952438ad509f71c
    resource: repo://scripts/check_versions.py
  - id: openwiki-source-69c8fbb2b27ed8bbfd303378
    resource: repo://scripts/pre-push-pipeline.sh
generated: { by: "hermes", at: "2026-11-25T23:47:00.311Z" }
---

# Version pinning, drift detection and release gates

This repository packages upstream software rather than developing it, so release safety means keeping two pins aligned and making every published change pass an assessment gate. The API/UI pairing invariant, the daily drift watch and the two enforcement layers are described here; the contents of the regression suites are covered in [Regression suites and precommit gate](../workflows/testing-and-regressions.md).

## The version-pair invariant

`hindsight/Dockerfile` installs `hindsight-api-slim[embedded-db,local-llm,local-onnx]==1.2.3` into `/opt/hindsight-venv` and `@vectorize-io/hindsight-control-plane@1.2.3` into `/opt/control-plane`; `hindsight/versions.json` records the same pair as `hindsight_api` and `control_plane` (`repo://hindsight/Dockerfile#L57-L90`, `repo://hindsight/versions.json#L1-L4`). API and UI versions must match: a mismatch shows up as UI 404s and empty memory tabs, so both pins are bumped together in one release (`repo://README.md#L124-L129`). The separate `version` field in `hindsight/config.yaml` is the add-on release version that Home Assistant uses to offer an update; a change that must reach installed users requires bumping it, followed by a store reload (`POST /addons/reload`) and verification of the direct UI and the sidebar panel (`repo://hindsight/config.yaml#L76-L78`, `repo://README.md#L143`).

## Daily drift detection

`scripts/check_versions.py` compares the recorded and pinned versions with the npm latest tag for the Control Plane and the PyPI latest version for the API. Comparison uses numeric version tuples, so suffixes such as `.post1` do not create false drift (`repo://scripts/check_versions.py#L22-L56`, `repo://hindsight/tests/test_version_watch.py#L98-L103`). Drift is reported separately for the API record, the Control Plane record and the Dockerfile pin; with no `--create-task` flag a drift exits 2, a fetch failure exits 3 and an up-to-date check exits 0 (`repo://scripts/check_versions.py#L104-L125`, `repo://hindsight/tests/test_version_watch.py#L149-L183`).

With `--create-task`, the drift report opens one Kanban assessment task on the `hindsight-haos` project, keyed `version-watch-<api>-<cp>` so repeated daily runs do not create duplicates. The task instructs the agent to verify compatibility, update `versions.json` and the Dockerfile pin together, update README/DOCS/CHANGELOG and the add-on version, run the regression suites and follow the normal PR flow. The script never edits pins or runtime code itself; the decision to ship stays with the assessment pipeline (`repo://scripts/check_versions.py#L68-L101`, `repo://README.md#L130-L134`). `hindsight/tests/test_version_watch.py` verifies this offline by stubbing both the registry fetch and `subprocess.run`, including the idempotency key and command shape (`repo://hindsight/tests/test_version_watch.py#L111-L147`).

## Pre-push assessment gate

`scripts/setup-hooks.sh` installs the local gate either globally (a dispatcher under `~/.hermes/git-hooks` that only fires for origins containing `hindsight-haos`) or as a per-clone `core.hooksPath`; `.githooks/pre-push` simply execs `scripts/pre-push-pipeline.sh` (`repo://scripts/setup-hooks.sh#L4-L18`, `repo://scripts/setup-hooks.sh#L20-L40`, `repo://.githooks/pre-push#L1-L4`).

The pipeline derives a change-set key from the first unpushed commit that lacks a `Pipeline-Key:` trailer, grouping full multi-line commit bodies so the assessment commit itself does not start a new task (`repo://scripts/pre-push-pipeline.sh#L17-L35`). It then reads the matching Kanban task status: `done` runs the five regression suites and allows the push; `none` creates a keyed goal-mode assessment task and blocks; any other status blocks until the task finishes (`repo://scripts/pre-push-pipeline.sh#L37-L108`). The assessment is told to review the diff, refresh README/DOCS and tests, report exact commands and results, and leave edits uncommitted so the parent can commit them with the stable `Pipeline-Key` trailer (`repo://scripts/pre-push-pipeline.sh#L81-L101`). `hindsight/tests/test_prepush_pipeline.py` exercises key derivation with real multi-line git bodies, the all-pipeline-commits fallback, board-status detection and fail-closed behavior (`repo://hindsight/tests/test_prepush_pipeline.py#L1-L8`, `repo://hindsight/tests/test_prepush_pipeline.py#L251-L253`, `repo://hindsight/tests/test_prepush_pipeline.py#L322-L333`).

## GitHub-side gate

Branch protection on `main` requires a pull request and the `regression` status check from `.github/workflows/regression-tests.yml`, which runs all five standalone suites on Python 3.12 for pushes and pull requests. This check is server-side: `--no-verify` can skip the local hook but cannot bypass the required check (`repo://.github/workflows/regression-tests.yml#L1-L27`, `repo://README.md#L145-L157`). Release discipline, add-on auto-update and the cold backup contract are described in [Add-on runtime and process topology](../architecture/addon-runtime.md) and the README stability section (`repo://README.md#L135-L143`).

---
type: architecture
title: Add-on runtime and process topology
description: How the Hindsight HAOS image is built and booted, from the pinned API and control-plane packages through the entrypoint, cont-init scripts, PostgreSQL/pgvector, the long-running services and shutdown handling.
tags: [home-assistant, add-on, runtime, s6, postgresql]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-25T23:47:00.311Z
sources:
  - id: openwiki-source-150ac6e3b9a2e0438493c07a
    resource: repo://hindsight/config.yaml
  - id: openwiki-source-10e42256adf0eb31d263190b
    resource: repo://hindsight/Dockerfile
  - id: openwiki-source-764c11aff20505b75fcae64f
    resource: repo://hindsight/ha_entrypoint.sh
  - id: openwiki-source-bcf0a40326b67432ed42877e
    resource: repo://hindsight/rootfs/etc/cont-init.d/20-postgres.sh
  - id: openwiki-source-072c3d0308f1def0b649c890
    resource: repo://hindsight/rootfs/etc/services.d/hindsight/finish
  - id: openwiki-source-fcec0817d255962190de1380
    resource: repo://hindsight/rootfs/etc/services.d/hindsight/run
  - id: openwiki-source-dc937830b80bdb633b7f5f89
    resource: repo://hindsight/versions.json
generated: { by: "hermes", at: "2026-11-25T23:47:00.311Z" }
---

# Add-on runtime and process topology

This page describes the container-side machinery that turns the add-on options into a running memory service. It covers image composition, the PID 1 entrypoint, cont-init preparation, the two long-running services, persistence and health/shutdown behavior. Option translation itself is covered in [Configuration and model provider selection](../architecture/configuration-and-models.md), and the web UI proxy is covered in [Control plane and Home Assistant ingress](../architecture/ingress-and-control-plane.md).

## Responsibility and boundaries

The repository is a Home Assistant add-on, not a fork of Hindsight. It packages the upstream API and Control Plane at matching pinned versions, adds PostgreSQL with pgvector, a minimal bashio compatibility layer, and startup/shutdown orchestration. `hindsight/config.yaml` declares the Supervisor contract: `init: false`, `startup: services`, ingress on port 9997, exposed ports 8888 and 9999, `backup: cold`, and a watchdog against `http://[HOST]:[PORT:8888]/health` (`repo://hindsight/config.yaml#L1-L13`, `repo://hindsight/config.yaml#L73-L78`).

## Image composition

`hindsight/build.json` pins both architectures to `ghcr.io/hassio-addons/debian-base:9.5.1`. The Dockerfile copies `rootfs/` into the image, installs PostgreSQL 15 with `postgresql-15-pgvector`, Python, jq and nginx, then installs:

- the API as `hindsight-api-slim[embedded-db,local-llm,local-onnx]==1.2.3` into `/opt/hindsight-venv`, so the local llama.cpp and ONNX extras are available without a key (`repo://hindsight/Dockerfile#L57-L67`);
- the Control Plane from `@vectorize-io/hindsight-control-plane@1.2.3` into `/opt/control-plane`, copying its `standalone/` directory to the root because `server.js` is looked up there (`repo://hindsight/Dockerfile#L69-L90`).

`hindsight/versions.json` records the same API and control-plane pair as the image (`repo://hindsight/versions.json#L1-L4`). Keeping these versions equal is a release invariant: mismatch shows up as UI 404s and empty memory tabs.

The image deliberately overrides the base entrypoint with `ENTRYPOINT ["/usr/bin/env"]` and `CMD ["/ha_entrypoint.sh"]` (`repo://hindsight/Dockerfile#L110-L119`). That is the reason the entrypoint has to recreate parts of the s6 environment itself.

## Boot sequence

`ha_entrypoint.sh` is the PID 1 process under `init: false`. Its phases are:

1. **PID 1 detection and signal trap.** When `$$` is 1 it links `/command/*` into `/usr/bin/` and installs `terminate()` for SIGTERM/SIGINT. The trap is registered early because the kernel discards signals whose handler is still `SIG_DFL`; if it were installed after the Supervisor probe and cont-init chain, an early stop would be lost and Home Assistant would wait out the grace period and report a failed add-on. The handler runs with `set +e`, forwards TERM to its direct children and exits 0 (`repo://hindsight/ha_entrypoint.sh#L8-L17`, `repo://hindsight/ha_entrypoint.sh#L23-L65`).
2. **Shebang selection.** A probe script tests a list of candidate shebangs by actually executing a tiny file; `bashio::app.version` must return a non-empty, non-null value. The chosen shebang is later substituted into cont-init and service scripts with `sed` (`repo://hindsight/ha_entrypoint.sh#L99-L217`, `repo://hindsight/ha_entrypoint.sh#L399-L400`).
3. **s6 environment seeding.** Because stage 1 never ran, the script dumps the container environment into `/run/s6/container_environment` when `with-contenv` is present. It fills a sibling `.tmp` directory and renames it into place so a concurrent reader sees either no directory or a complete one; a partially populated envdir could start a `with-contenv` script with a missing `SUPERVISOR_TOKEN` (`repo://hindsight/ha_entrypoint.sh#L219-L270`).
4. **bashio fallback and Supervisor wait.** The real bashio library is preferred; otherwise `bashio-standalone.sh` supplies an environment/JSON-backed shim. `wait_for_supervisor()` is bounded by `HA_SUPERVISOR_WAIT` (default 30s), requires a token and the full library, and probes bashio's cached `/addons/self/info` via `bashio::app.ip_address` so later ingress lookups hit the cache (`repo://hindsight/ha_entrypoint.sh#L276-L294`, `repo://hindsight/ha_entrypoint.sh#L296-L371`).
5. **Cont-init and services.** Every `/etc/cont-init.d/*` script is run once via `run_one_script()`, which rewrites its shebang and appends `exit 0`. In PID 1 mode each `/etc/services.d/*/run` is launched in its own subshell with a restart loop: a clean exit 0 stops restarting, a non-zero exit is retried up to five times with a 5-second delay, and TERM/INT forwards to the whole process group (`repo://hindsight/ha_entrypoint.sh#L377-L436`, `repo://hindsight/ha_entrypoint.sh#L438-L506`). The entrypoint then stays alive on `sleep infinity` (`repo://hindsight/ha_entrypoint.sh#L512-L526`).

## Cont-init preparation

`20-postgres.sh` initializes a fresh cluster at `${PGDATA:-/data/pg}` with `initdb --auth=trust`, appends loopback-only listener settings (`listen_addresses = '127.0.0.1'`, port 5432, 30 connections, `jit = off`) and trust rules to `pg_hba.conf`. It deliberately does not create the database or extension; that is deferred to the service that can verify PostgreSQL is accepting connections (`repo://hindsight/rootfs/etc/cont-init.d/20-postgres.sh#L9-L42`).

`30-config.sh` translates options into `/data/hindsight/env`, the file consumed by the API service. That translation is documented separately in [Configuration and model provider selection](../architecture/configuration-and-models.md).

## Long-running services

**Hindsight API service.** `hindsight/run` exports `HOME=/data/hindsight-home` so downloaded GGUF and ONNX models survive add-on updates, sources `/data/hindsight/env` with `set -a`, removes a stale `postmaster.pid` only when PostgreSQL is not answering, starts `pg_ctl` with `-w -t 60`, waits with `pg_isready`, creates the `hindsight` database if absent, enables the `vector` extension (warning rather than failing if unavailable), and finally `exec`s `/opt/hindsight-venv/bin/hindsight-api` (`repo://hindsight/rootfs/etc/services.d/hindsight/run#L13-L53`). The companion `finish` script stops PostgreSQL with `pg_ctl -m fast` when the service exits (`repo://hindsight/rootfs/etc/services.d/hindsight/finish#L5-L11`).

**Control plane service.** `control-plane/run` exits immediately when `control_plane != true`, waits up to 60 × 2s for `http://127.0.0.1:8888/health`, derives the ingress base path from the Supervisor's `ingress_url`, renders `nginx.conf.template` into `/run/nginx/hindsight.conf`, starts `node server.js` on the internal port 9998, and `exec`s nginx in the foreground (`repo://hindsight/rootfs/etc/services.d/control-plane/run#L14-L74`). See [Control plane and Home Assistant ingress](../architecture/ingress-and-control-plane.md).

## Persistence, health and failure behavior

All mutable state is under `/data`: the PostgreSQL cluster in `/data/pg`, the generated env file in `/data/hindsight/env`, and model caches in `/data/hindsight-home`. The add-on declares `backup: cold`, so Supervisor stops the container before backing up that directory (`repo://hindsight/config.yaml#L1-L5`).

Health has two layers: the Supervisor watchdog URL in `config.yaml` (`repo://hindsight/config.yaml#L77-L78`) and the Dockerfile `HEALTHCHECK`, which polls `http://127.0.0.1:8888/health` every 10s, allows a 600s start period for first-run model downloads, and gives up after 6 failures (`repo://hindsight/Dockerfile#L152-L163`). Failure handling is intentionally asymmetric: a failed PostgreSQL start is fatal in the service script, a missing pgvector extension is only a warning, and a crashed service script is restarted up to five times before the entrypoint gives up.

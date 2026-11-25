---
type: "Reference"
title: "Control plane and Home Assistant ingress"
openwiki_generated: true
verified:
  - by: openwiki/0.9.0
    at: 2026-11-25T23:47:00.311Z
sources:
  - id: openwiki-source-045bc20b55360a2c685b8ca5
    resource: repo://hindsight/rootfs/etc/nginx.conf.template
  - id: openwiki-source-0a3d7c05f6e1a163dada353c
    resource: repo://hindsight/rootfs/etc/services.d/control-plane/run
  - id: openwiki-source-a922bbc1f93dc44cd6e3c69e
    resource: repo://hindsight/tests/test_ingress_rewrite.py
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "hermes", at: "2026-11-25T23:47:00.311Z" }
---


# Control plane and Home Assistant ingress

The Control Plane is an upstream Next.js standalone server that emits root-absolute asset and API paths. Home Assistant ingress serves add-on UIs under a per-install prefix (`/api/hassio_ingress/<token>/`), so the add-on places an nginx layer in front of the UI and rewrites only the paths that are genuinely navigation paths. This page covers that proxy boundary; the API service itself is described in [Add-on runtime and process topology](../architecture/addon-runtime.md), and option handling in [Configuration and model provider selection](../architecture/configuration-and-models.md).

## Port topology and ownership

Four ports are in play (`repo://hindsight/config.yaml#L10-L13`, `repo://hindsight/config.yaml#L40-L45`, `repo://hindsight/rootfs/etc/services.d/control-plane/run#L14-L17`):

| Port | Owner | Role |
| --- | --- | --- |
| 8888 | Hindsight API | REST, MCP and `/health` watchdog |
| 9999 | nginx, direct server | LAN access to the UI, plain proxy without rewriting |
| 9997 | nginx, ingress server | Internal Home Assistant sidebar port, rewrites paths to the ingress base |
| 9998 | Next.js `server.js` | Loopback backend behind both nginx servers, not exposed publicly |

`config.yaml` declares ingress on 9997 with `ingress_entry: dashboard` and maps the direct UI to 9999; the README notes that the sidebar panel goes through ingress and needs no port forwarding (`repo://README.md#L39-L49`). Both nginx `server` blocks proxy to `http://127.0.0.1:__BACKEND__`, i.e. 9998.

## Startup sequence

`hindsight/rootfs/etc/services.d/control-plane/run` is the long-running service:

1. It exits cleanly when `control_plane` is not `true`, so disabling the UI does not create a restart loop (`repo://hindsight/rootfs/etc/services.d/control-plane/run#L14-L22`).
2. It polls `http://127.0.0.1:8888/health` up to 60 times at 2-second intervals before serving, so the UI never opens against a connection-refused dataplane (`repo://hindsight/rootfs/etc/services.d/control-plane/run#L24-L33`).
3. It reads `/addons/self/info` from the Supervisor with the add-on token, extracts `ingress_url` and strips its last segment to obtain the runtime base path. The path is installation-specific, so it cannot be baked into the image (`repo://hindsight/rootfs/etc/services.d/control-plane/run#L35-L45`).
4. It renders `/etc/nginx.conf.template` into `/run/nginx/hindsight.conf` by substituting `__DIRECT_PORT__`, `__PORT__`, `__BACKEND__` and `__BASE__` (`repo://hindsight/rootfs/etc/services.d/control-plane/run#L47-L52`).
5. It exports the backend port and dataplane URL (`HINDSIGHT_CP_DATAPLANE_API_URL=http://127.0.0.1:8888`), starts `node server.js` on 9998 with IPv4-first DNS, waits for `/dashboard` to answer, then `exec`s nginx in the foreground (`repo://hindsight/rootfs/etc/services.d/control-plane/run#L54-L74`). Foreground `exec` makes the container's PID 1 signal handling effective for the proxy.

## Why the base path is injected at runtime

Next.js builds its client router around a fixed base path, but the ingress token differs per install. The ingress template therefore injects a `<head>` script into each HTML response that sets `window.process.env.NEXT_PUBLIC_BASE_PATH` to the runtime value, so the UI's `withBasePath()` prefixes API calls exactly once (`repo://hindsight/rootfs/etc/nginx.conf.template#L62-L68`, `repo://hindsight/rootfs/etc/nginx.conf.template#L80-L82`). The same script intercepts clicks on ingress links and patches `history.pushState`/`replaceState` to force full page loads, because Next.js client-side navigation cannot handle the ingress prefix (`repo://hindsight/rootfs/etc/nginx.conf.template#L80-L82`).

## Rewrite rules and their limits

The ingress server clears `Accept-Encoding` so nginx `sub_filter` sees uncompressed URLs, then prefixes root-absolute assets (`href="/`, `src="/`, `action="/`, `url(/`, `_next`) with the base (`repo://hindsight/rootfs/etc/nginx.conf.template#L36-L61`). The direct server on 9999 intentionally has none of these rules (`repo://hindsight/rootfs/etc/nginx.conf.template#L10-L27`).

Only two template literals are treated as navigation paths: `` `/banks `` and `` `/knowledge-banks ``. Other route-like strings such as `/memories-timeseries`, `/observations`, `/mental-models`, `/directives` and `/webhooks` are API path suffixes appended to `/api/banks/<id>`; prefixing them would produce URLs like `/api/banks/<id>/<base>/memories-timeseries` and HTTP 404s (`repo://hindsight/rootfs/etc/nginx.conf.template#L62-L75`). The bank selector parses the current location with `^\\/banks\\/...`, so its regex is rewritten to `^.*\\/banks\\/` to tolerate the ingress prefix; without it the bank dropdown cannot select a bank (`repo://hindsight/rootfs/etc/nginx.conf.template#L76-L78`). Both servers send `Cache-Control: no-store` on every response, and the ingress server hides the upstream Content-Security-Policy header so injected scripts are not blocked (`repo://hindsight/rootfs/etc/nginx.conf.template#L25-L26`, `repo://hindsight/rootfs/etc/nginx.conf.template#L84-L85`, `repo://README.md#L138-L140`).

## Regression coverage

`hindsight/tests/test_ingress_rewrite.py` reads the actual template, extracts its `sub_filter` rules in order and applies them to representative HTML/JS fixtures. It asserts that no rule rewrites an API suffix literal, that both navigation builders and the bank-selector regex are still rewritten, that `NEXT_PUBLIC_BASE_PATH` is injected into `<head>`, and that a prefixed bank URL and regex work while `/memories-timeseries` and `/observations` stay bare (`repo://hindsight/tests/test_ingress_rewrite.py#L29-L43`, `repo://hindsight/tests/test_ingress_rewrite.py#L86-L140`). This suite is the guard to run before changing the template; see [Regression suites and precommit gate](../workflows/testing-and-regressions.md).

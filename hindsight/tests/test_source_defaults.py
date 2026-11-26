#!/usr/bin/env python3
"""Guard the source config defaults so a credential or forced expert route never
lands in the public repo. Runtime routing (e.g. an OmniRoute combo via Supervisor
options) is a per-install setting and must not be baked into config.yaml.

Also guards llm_base_url: it must have an empty default in options (so it
shows in the Configuration tab) and a non-optional `str` schema type matching
that default. An optional (`str?`) key with a default contradicts HA's rules.

Finally it guards the Ponytail rung-1 removals: the dead remote-code installer
(ha_autoapps.sh + its Dockerfile wiring), the dead `ingress` option/schema key,
and the unused `embedded-db` pip extra. The checks fail if any of them returns,
and also verify the behaviour that replaced them (top-level ingress and the
local-llm/local-onnx extras) stays intact.

It also guards the release metadata: versions.json, both pins in the
Dockerfile, the add-on version and the consolidation-incident troubleshooting
sections in README/DOCS must agree.

No third-party deps: parses the small options/schema blocks with string checks.
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CFG = REPO / "hindsight" / "config.yaml"
DOCKERFILE = REPO / "hindsight" / "Dockerfile"
AUTOAPPS = REPO / "hindsight" / "ha_autoapps.sh"
VERSIONS = REPO / "hindsight" / "versions.json"
README = REPO / "README.md"
DOCS = REPO / "hindsight" / "DOCS.md"


def main() -> int:
    errors = []
    text = CFG.read_text()
    options = text.split("options:", 1)[1].split("schema:", 1)[0] if "options:" in text else ""
    schema = text.split("schema:", 1)[1] if "schema:" in text else ""

    def opt(name):
        for line in options.splitlines():
            line = line.strip()
            if line.startswith(f"{name}:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
        return None

    def schema_type(name):
        for line in schema.splitlines():
            line = line.strip()
            if line.startswith(f"{name}:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
        return None

    key = opt("llm_api_key") or ""
    if key and key != '""':
        errors.append(f"llm_api_key must be empty in source config, got {key[:8]}...")

    if opt("mode") != "simple":
        errors.append(f"mode must default to 'simple' for a no-key install, got {opt('mode')!r}")
    if opt("llm_provider") != "llamacpp":
        errors.append(f"llm_provider must default to local 'llamacpp', got {opt('llm_provider')!r}")

    # llm_base_url must be a UI-visible, empty-by-default option. A `str?`
    # schema type with a default contradicts Home Assistant's option/schema rules.
    base_url = opt("llm_base_url")
    if base_url is None:
        errors.append("llm_base_url must be present in options so it appears in the UI")
    elif base_url != "":
        errors.append(f"llm_base_url default must be empty in source config, got {base_url[:40]!r}")
    url_type = schema_type("llm_base_url")
    if url_type != "str":
        errors.append(f"llm_base_url schema must be 'str' (it has a default), got {url_type!r}")

    # No credential-looking token anywhere in the source config.
    if "sk-" in text:
        errors.append("source config contains an 'sk-' token (possible credential leak)")

    # Version must be a quoted string.
    for line in text.splitlines():
        if line.startswith("version:"):
            v = line.split(":", 1)[1].strip()
            if not (v.startswith('"') and v.endswith('"')):
                errors.append("version must be a quoted string")
            break

    # Ponytail rung 1: the dead installer downloaded and eval'd a remote script
    # for an empty package list. Neither it nor its Dockerfile wiring may stay.
    if AUTOAPPS.exists():
        errors.append("hindsight/ha_autoapps.sh must be deleted (dead remote installer)")
    docker = DOCKERFILE.read_text() if DOCKERFILE.is_file() else ""
    if not docker:
        errors.append("hindsight/Dockerfile is missing")
    for token in ("ha_autoapps", "ha_automatic_packages", "PACKAGES"):
        if token in docker:
            errors.append(f"Dockerfile still references {token!r}")

    # Ingress is forced by the top-level keys and the control-plane service;
    # the unused options/schema toggle must not reappear as a dead UI control.
    for block_name, block in (("options", options), ("schema", schema)):
        for line in block.splitlines():
            if line.strip().startswith("ingress:"):
                errors.append(f"config.yaml {block_name} still defines {line.strip()!r}")
    top_level = {}
    for line in text.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key_name, value = line.split(":", 1)
            top_level[key_name.strip()] = value.strip()
    for key_name, expected in (
        ("ingress", "true"),
        ("ingress_port", "9997"),
        ("ingress_entry", "dashboard"),
    ):
        if top_level.get(key_name) != expected:
            errors.append(
                f"top-level {key_name} must stay {expected!r}, got {top_level.get(key_name)!r}"
            )

    # embedded-db (pg0) is never used: 30-config.sh hardcodes the PostgreSQL 15
    # URL. Only the two local-model extras should be requested, at the same pin.
    if "embedded-db" in docker:
        errors.append("Dockerfile still mentions the unused 'embedded-db' extra")
    extras_line = next(
        (line.strip() for line in docker.splitlines() if "hindsight-api-slim[" in line),
        None,
    )
    if extras_line is None:
        errors.append("Dockerfile no longer pins hindsight-api-slim extras")
    elif not (
        extras_line.startswith('"hindsight-api-slim[local-llm,local-onnx]==')
        and extras_line.endswith('"')
    ):
        errors.append(
            f"hindsight-api-slim must pin [local-llm,local-onnx] extras, got {extras_line!r}"
        )
    if "postgresql-15" not in docker:
        errors.append("Dockerfile must keep installing PostgreSQL 15")

    # Release metadata: add-on 1.2.25 ships upstream 1.3.0 in both components.
    try:
        versions = json.loads(VERSIONS.read_text())
    except (OSError, ValueError) as exc:
        errors.append(f"hindsight/versions.json is not valid JSON: {exc}")
        versions = {}
    for component in ("hindsight_api", "control_plane"):
        value = versions.get(component)
        if value != "1.3.0":
            errors.append(f"versions.json {component} must be 1.3.0, got {value!r}")
    api_pin = re.search(r"hindsight-api-slim\[[^\]]+\]==([0-9.]+)", docker)
    cp_pin = re.search(r"hindsight-control-plane@([0-9.]+)", docker)
    if not api_pin or api_pin.group(1) != "1.3.0":
        errors.append(
            f"Dockerfile API pin must be 1.3.0, got {api_pin.group(1) if api_pin else None!r}"
        )
    if not cp_pin or cp_pin.group(1) != "1.3.0":
        errors.append(
            f"Dockerfile control-plane pin must be 1.3.0, got {cp_pin.group(1) if cp_pin else None!r}"
        )
    if top_level.get("version") != '"1.2.25"':
        errors.append(f"add-on version must be 1.2.25, got {top_level.get('version')!r}")

    # The consolidation backlog is handled at runtime, so the operational
    # guidance must ship in both docs with the real diagnostic endpoints.
    for name, doc in (("README.md", README), ("hindsight/DOCS.md", DOCS)):
        dtext = doc.read_text() if doc.is_file() else ""
        for token in (
            "consolidation_state=pending",
            "operations?type=consolidation",
            "llm-requests",
            "HINDSIGHT_API_LLM_MODEL",
            '{"updates":{',
        ):
            if token not in dtext:
                errors.append(f"{name} missing consolidation troubleshooting token {token!r}")
        if not re.search(r"(?is)\*\*(?:do not|never)\s+delete\s+pending\s+memories", dtext):
            errors.append(f"{name} must warn against deleting pending memories")

    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1
    print(
        "source defaults OK: simple/llamacpp, empty api key and base URL, "
        "str base-URL schema, quoted version, no token, no dead installer/"
        "ingress option/embedded-db extra"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Guard the source config defaults so a credential or forced expert route never
lands in the public repo. Runtime routing (e.g. an OmniRoute combo via Supervisor
options) is a per-install setting and must not be baked into config.yaml.

Also guards llm_base_url: it must have an empty default in options (so it
shows in the Configuration tab) and a non-optional `str` schema type matching
that default. An optional (`str?`) key with a default contradicts HA's rules.

No third-party deps: parses the small options/schema blocks with string checks.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CFG = REPO / "hindsight" / "config.yaml"


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

    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1
    print(
        "source defaults OK: simple/llamacpp, empty api key and base URL, "
        "str base-URL schema, quoted version, no token"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

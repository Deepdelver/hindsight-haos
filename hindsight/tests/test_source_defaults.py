#!/usr/bin/env python3
"""Guard the source config defaults so a credential or forced expert route never
lands in the public repo. Runtime routing (e.g. an OmniRoute combo via Supervisor
options) is a per-install setting and must not be baked into config.yaml.

No third-party deps: parses the small options block with plain string checks.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CFG = REPO / "hindsight" / "config.yaml"

def main() -> int:
    errors = []
    text = CFG.read_text()
    options = text.split("options:", 1)[1].split("schema:", 1)[0] if "options:" in text else ""

    def opt(name):
        for line in options.splitlines():
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
    print("source defaults OK: simple/llamacpp, empty api key, quoted version, no token")
    return 0

if __name__ == "__main__":
    sys.exit(main())

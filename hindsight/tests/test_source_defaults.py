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
local-llm/local-onnx extras) stays intact. It also runs the real entrypoint
twice over one cont-init script (exec and source mode), so a script cannot be
neutered between starts by an injected `exit 0`.

It also guards the release metadata: versions.json, both pins in the
Dockerfile, the add-on version and the consolidation-incident troubleshooting
sections in README/DOCS must agree.

No third-party deps: parses the small options/schema blocks with string checks.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CFG = REPO / "hindsight" / "config.yaml"
DOCKERFILE = REPO / "hindsight" / "Dockerfile"
AUTOAPPS = REPO / "hindsight" / "ha_autoapps.sh"
ENTRYPOINT = REPO / "hindsight" / "ha_entrypoint.sh"
VERSIONS = REPO / "hindsight" / "versions.json"
README = REPO / "README.md"
DOCS = REPO / "hindsight" / "DOCS.md"

# A cont-init script that does observable work on every invocation. The entrypoint
# must not be able to turn this into a no-op between starts.
WORK_SCRIPT = """\
#!/bin/bash
printf 'work\\n' >> "$WORK_LOG"
"""


def run_entrypoint_twice(workdir, source_mode):
    """Run a copy of the real entrypoint twice over the same cont-init script.

    Only the absolute script directories and the shebang candidate list are
    redirected inside ``workdir``: the copy keeps the real run_one_script body,
    chown/chmod, shebang rewrite, supervisor wait and source/exec fallback. The
    candidate list is narrowed to /bin/bash so the probe does not depend on
    which bashio shims happen to exist on the machine running the test.
    """
    init_dir = workdir / "cont-init.d"
    init_dir.mkdir(parents=True, exist_ok=True)
    (workdir / "services.d").mkdir(exist_ok=True)
    (workdir / "s6-rc.d").mkdir(exist_ok=True)

    text = ENTRYPOINT.read_text()
    for original, replacement in (
        ("/etc/cont-init.d", str(init_dir)),
        ("/etc/services.d", str(workdir / "services.d")),
        ("/etc/s6-overlay/s6-rc.d", str(workdir / "s6-rc.d")),
    ):
        text = text.replace(original, replacement)
    text, count = re.subn(
        r"candidate_shebangs=\([^)]*\)",
        'candidate_shebangs=(\n  "/bin/bash"\n)',
        text,
        count=1,
    )
    if count != 1:
        raise AssertionError("entrypoint candidate_shebangs array not found")

    entry = workdir / "ha_entrypoint.sh"
    entry.write_text(text)
    entry.chmod(0o700)

    script = init_dir / "10-work.sh"
    script.write_text(WORK_SCRIPT)
    script.chmod(0o700)

    work_log = workdir / "work.log"
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "WORK_LOG": str(work_log),
        "HA_SUPERVISOR_WAIT": "0",
    }
    if source_mode:
        env["ha_entry_source"] = "true"

    runs = []
    for _ in range(2):
        runs.append(
            subprocess.run(
                ["bash", str(entry)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(workdir),
                timeout=60,
            )
        )
    lines = work_log.read_text().splitlines() if work_log.exists() else []
    body = script.read_text().splitlines()
    injected = [line for line in body if line.strip() == "exit 0"]
    return runs, lines, injected


def check_entrypoint_idempotence():
    """Ponytail rung 1 / F3: no injected `exit 0`, real work on every start."""
    errors = []
    if not ENTRYPOINT.is_file():
        return ["hindsight/ha_entrypoint.sh is missing"]

    source = ENTRYPOINT.read_text()
    if "sed -i '1a exit 0'" in source:
        errors.append("entrypoint still writes 'exit 0' into cont-init scripts")

    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        for source_mode in (False, True):
            label = "source" if source_mode else "exec"
            case_dir = td / label
            case_dir.mkdir()
            runs, lines, injected = run_entrypoint_twice(case_dir, source_mode)
            rcs = [run.returncode for run in runs]
            if any(rc != 0 for rc in rcs):
                detail = " | ".join((run.stdout + run.stderr).strip()[-400:] for run in runs)
                errors.append(f"entrypoint {label} run failed: rc={rcs}: {detail}")
            if len(lines) != 2:
                errors.append(
                    f"entrypoint {label}: second run skipped the real work "
                    f"(expected 2 work lines, got {lines!r})"
                )
            if injected:
                errors.append(f"entrypoint {label}: script got an injected exit 0: {injected}")
    return errors


def release_metadata_errors(versions_text, docker_text, config_text):
    """Cross-check release metadata across versions.json, Dockerfile and config.yaml.

    Expected values are derived from the sources themselves — no literal release
    numbers live in this guard:

      * versions.json records the upstream release; its two component entries
        must be present and agree with each other;
      * both Dockerfile pins must match the matching versions.json entry;
      * config.yaml carries the add-on's own release number, read dynamically
        (independent of the upstream version) and required to be a quoted
        string.

    Keeping the check in one pure function lets a consistent bump be verified
    with synthetic sources (see self_test_consistent_bump) so a release bump
    never makes this guard fail on hardcoded expectations again.
    """
    errors = []

    try:
        versions = json.loads(versions_text)
    except (TypeError, ValueError) as exc:
        errors.append(f"hindsight/versions.json is not valid JSON: {exc}")
        versions = {}
    if not isinstance(versions, dict):
        errors.append(
            f"hindsight/versions.json must be a JSON object, got {type(versions).__name__}"
        )
        versions = {}

    api_recorded = versions.get("hindsight_api")
    cp_recorded = versions.get("control_plane")
    for component, value in (("hindsight_api", api_recorded), ("control_plane", cp_recorded)):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"versions.json {component} must be a version string, got {value!r}")
    if api_recorded != cp_recorded:
        errors.append(
            "versions.json components must agree: "
            f"hindsight_api={api_recorded!r}, control_plane={cp_recorded!r}"
        )

    api_pin_match = re.search(r"hindsight-api-slim\[[^\]]+\]==([0-9][0-9A-Za-z.\-]*)", docker_text)
    cp_pin_match = re.search(r"hindsight-control-plane@([0-9][0-9A-Za-z.\-]*)", docker_text)
    api_pin = api_pin_match.group(1) if api_pin_match else None
    cp_pin = cp_pin_match.group(1) if cp_pin_match else None
    if api_pin != api_recorded:
        errors.append(
            f"Dockerfile API pin must match versions.json hindsight_api "
            f"({api_recorded!r}), got {api_pin!r}"
        )
    if cp_pin != cp_recorded:
        errors.append(
            f"Dockerfile control-plane pin must match versions.json control_plane "
            f"({cp_recorded!r}), got {cp_pin!r}"
        )

    addon_version = next(
        (
            line.split(":", 1)[1].strip()
            for line in config_text.splitlines()
            if line.startswith("version:")
        ),
        None,
    )
    if addon_version is None:
        errors.append("config.yaml has no top-level version")
    elif not (addon_version.startswith('"') and addon_version.endswith('"')):
        errors.append(
            f"add-on version in config.yaml must be a quoted string, got {addon_version!r}"
        )

    return errors


def _synthetic_release_sources(upstream, addon):
    """Build the three release sources with the given (bumped) versions."""
    versions_text = json.dumps({"hindsight_api": upstream, "control_plane": upstream})
    docker_text = (
        f'RUN pip install "hindsight-api-slim[local-llm,local-onnx]=={upstream}"\n'
        f"RUN npm install @vectorize-io/hindsight-control-plane@{upstream}\n"
    )
    config_text = (
        "ingress: true\n"
        "options:\n"
        "  mode: simple\n"
        "schema:\n"
        "  mode: list(simple|expert)\n"
        f'version: "{addon}"\n'
    )
    return versions_text, docker_text, config_text


def self_test_consistent_bump():
    """Prove a bump applied to all three sources keeps the guard green.

    Deliberately different numbers (not the currently shipped ones) make this
    test fail if any literal version expectation sneaks back into the guard.
    """
    ok = True
    versions_text, docker_text, config_text = _synthetic_release_sources("9.8.7", "4.5.6")
    problems = release_metadata_errors(versions_text, docker_text, config_text)
    if problems:
        print("FAIL  consistent release bump should pass:", "; ".join(problems))
        ok = False
    else:
        print("PASS  consistent release bump across versions.json/Dockerfile/config.yaml")

    # A partial bump (Dockerfile API pin lagging versions.json) must be caught,
    # proving the cross-source consistency check is real, not a no-op.
    lagging_docker = (
        'RUN pip install "hindsight-api-slim[local-llm,local-onnx]==9.8.6"\n'
        "RUN npm install @vectorize-io/hindsight-control-plane@9.8.7\n"
    )
    problems = release_metadata_errors(versions_text, lagging_docker, config_text)
    if not any("API pin" in problem for problem in problems):
        print("FAIL  partial release bump should be detected:", "; ".join(problems))
        ok = False
    else:
        print("PASS  lagging Dockerfile pin is detected")
    return ok


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

    # Dedicated consolidation-LLM route (1.2.26): four expert-mode options with
    # EMPTY defaults. Unset means "reuse the normal LLM settings", so the source
    # config must carry no credential and no forced consolidation route. The
    # schema types mirror the main LLM options: str for free-text values and
    # password for the key (both non-optional because they have a "" default).
    consolidation_schema = {
        "consolidation_llm_provider": "str",
        "consolidation_llm_model": "str",
        "consolidation_llm_base_url": "str",
        "consolidation_llm_api_key": "password",
    }
    for name, expected_type in consolidation_schema.items():
        value = opt(name)
        if value is None:
            errors.append(f"{name} must be present in options so it appears in the UI")
        elif value != "":
            errors.append(f"{name} default must be empty in source config, got {value[:40]!r}")
        actual_type = schema_type(name)
        if actual_type != expected_type:
            errors.append(f"{name} schema must be '{expected_type}', got {actual_type!r}")

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

    # Release metadata: derive the expected values from the sources themselves
    # (versions.json <-> both Dockerfile pins, plus the add-on version in
    # config.yaml) so a consistent bump never trips a hardcoded expectation.
    try:
        versions_text = VERSIONS.read_text()
    except OSError as exc:
        errors.append(f"cannot read hindsight/versions.json: {exc}")
        versions_text = ""
    errors.extend(release_metadata_errors(versions_text, docker, text))

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

    # Ponytail rung 1 / F3: a start script must still do its real work on the
    # next start, in both exec and source mode.
    errors.extend(check_entrypoint_idempotence())

    # Release-metadata self-test: a consistent bump must never make this guard
    # fail on hardcoded expectations again (Ponytail rung 2/3).
    if not self_test_consistent_bump():
        errors.append("release bump self-test failed")

    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1
    print(
        "source defaults OK: simple/llamacpp, empty api key and base URL, "
        "str base-URL schema, four empty consolidation options with matching "
        "schema, quoted version, no token, no dead installer/ingress option/"
        "embedded-db extra, release versions consistent across "
        "versions.json/Dockerfile/config.yaml"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

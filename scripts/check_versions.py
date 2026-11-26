#!/usr/bin/env python3
"""Check whether upstream Hindsight releases moved past the versions in the add-on.

Without --create-task this only reports and exits 2 when an update is available.
With --create-task it opens one idempotent Kanban assessment task on the
hindsight-haos board; the normal agent assessment/release pipeline then decides
whether and how to bump pins and ship a new add-on version.

Run: python3 scripts/check_versions.py [--create-task]
"""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "hindsight" / "Dockerfile"
VERSIONS = ROOT / "hindsight" / "versions.json"
NPM_URL = "https://registry.npmjs.org/@vectorize-io%2Fhindsight-control-plane/latest"
PYPI_URL = "https://pypi.org/pypi/hindsight-api-slim/json"
BOARD = "hindsight-haos"
PROJECT = "hindsight-haos"


def vtuple(value):
    return tuple(int(p) for p in re.findall(r"\d+", str(value))[:3])


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


def pinned_control_plane():
    match = re.search(
        r"@vectorize-io/hindsight-control-plane@([0-9][0-9A-Za-z.\-]*)", DOCKERFILE.read_text()
    )
    return match.group(1) if match else None


def recorded_versions():
    data = json.loads(VERSIONS.read_text())
    return data.get("hindsight_api"), data.get("control_plane")


def assess(api_latest, cp_latest):
    api_recorded, cp_recorded = recorded_versions()
    cp_pinned = pinned_control_plane()
    drift = {
        "api": bool(vtuple(api_latest) > vtuple(api_recorded)),
        "control_plane": bool(vtuple(cp_latest) > vtuple(cp_recorded)),
        "pin": bool(cp_pinned and vtuple(cp_latest) > vtuple(cp_pinned)),
    }
    return {
        "recorded_api": api_recorded,
        "recorded_control_plane": cp_recorded,
        "pinned_control_plane": cp_pinned,
        "latest_api": api_latest,
        "latest_control_plane": cp_latest,
        "drift": drift,
        "update_available": any(drift.values()),
    }


def create_task(report):
    key = "version-watch-" + report["latest_api"] + "-" + report["latest_control_plane"]
    body = (
        "Upstream Hindsight version drift detected by the daily version watch.\n\n"
        f"Recorded API: {report['recorded_api']} -> latest {report['latest_api']}\n"
        f"Recorded control plane: {report['recorded_control_plane']} -> latest {report['latest_control_plane']}\n"
        f"Dockerfile pin: {report['pinned_control_plane']}\n\n"
        "Do this:\n"
        "1. Verify the releases and compatibility (API and control plane must match).\n"
        "2. Update hindsight/versions.json and the control-plane pin in the Dockerfile.\n"
        "3. Update README.md / hindsight/DOCS.md and CHANGELOG.md; bump config.yaml version.\n"
        "4. Run all five regression suites in hindsight/tests/: test_source_defaults.py,\n"
        "   test_ingress_rewrite.py, test_prepush_pipeline.py, test_version_watch.py\n"
        "   and test_continit_providers.py.\n"
        "5. Follow the normal Kanban assessment and PR/release flow. Do not push directly.\n"
    )
    result = subprocess.run(
        [
            "hermes",
            "kanban",
            "create",
            "Assess Hindsight upstream version drift",
            "--project",
            PROJECT,
            "--assignee",
            "default",
            "--idempotency-key",
            key,
            "--body",
            body,
        ],
        capture_output=True,
        text=True,
    )
    return key, result.returncode, (result.stdout + result.stderr).strip()


def main():
    create = "--create-task" in sys.argv
    try:
        npm = fetch_json(NPM_URL)
        pypi = fetch_json(PYPI_URL)
        report = assess(pypi["info"]["version"], npm["version"])
    except Exception as exc:
        print(f"Version watch failed: {exc}", file=sys.stderr)
        return 3

    print(json.dumps(report, indent=2))
    if not report["update_available"]:
        print("Up to date.")
        return 0
    print("Update available.")
    if create:
        key, rc, output = create_task(report)
        print(f"Kanban task key: {key} (create rc={rc})")
        if output:
            print(output[-500:])
        return 0 if rc == 0 else 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

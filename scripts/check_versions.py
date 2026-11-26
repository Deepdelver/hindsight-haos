#!/usr/bin/env python3
"""Check whether upstream Hindsight releases moved past the versions in the add-on.

Without --create-task this only reports and exits 2 when an update is available.
With --create-task it opens one idempotent Zero Factory task on the
deepdelver-hindsight-haos board; the normal factory pipeline then decides
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


def pinned_api():
    match = re.search(
        r"hindsight-api-slim\[[^\]]*\]==([0-9][0-9A-Za-z.\-]*)", DOCKERFILE.read_text()
    )
    return match.group(1) if match else None


def recorded_versions():
    data = json.loads(VERSIONS.read_text())
    return data.get("hindsight_api"), data.get("control_plane")


def assess(api_latest, cp_latest):
    api_recorded, cp_recorded = recorded_versions()
    cp_pinned = pinned_control_plane()
    api_pinned = pinned_api()
    drift = {
        "api": bool(vtuple(api_latest) > vtuple(api_recorded)),
        "control_plane": bool(vtuple(cp_latest) > vtuple(cp_recorded)),
        "pin": bool(cp_pinned and vtuple(cp_latest) > vtuple(cp_pinned)),
        "api_pin": bool(api_pinned and vtuple(api_pinned) != vtuple(api_recorded)),
    }
    return {
        "recorded_api": api_recorded,
        "recorded_control_plane": cp_recorded,
        "pinned_control_plane": cp_pinned,
        "pinned_api": api_pinned,
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
        f"Dockerfile API pin: {report['pinned_api']}\n"
        f"Dockerfile control-plane pin: {report['pinned_control_plane']}\n\n"
        "Do this:\n"
        "1. Verify the releases and compatibility (API and control plane must match).\n"
        "2. Update hindsight/versions.json and both Dockerfile pins so the API pin matches recorded_api.\n"
        "3. Update README.md / hindsight/DOCS.md and CHANGELOG.md; bump config.yaml version.\n"
        "4. Run all six regression suites in hindsight/tests/: test_source_defaults.py,\n"
        "   test_ingress_rewrite.py, test_prepush_pipeline.py, test_version_watch.py,\n"
        "   test_continit_providers.py and test_setup_gh_issues.py.\n"
        "5. Follow the Zero Factory flow: commit on a task branch, let the factory run precommit, open a PR, and let auto-merge + deployment handle the rest. Do not push directly to main.\n"
    )
    result = subprocess.run(
        [
            "hermes",
            "zerofactory",
            "create",
            "Assess Hindsight upstream version drift",
            "--description",
            body,
            "--board",
            "deepdelver-hindsight-haos",
            "--repo",
            "deepdelver-hindsight-haos",
            "--assignee",
            "zf-builder",
            "--status",
            "todo",
            "--priority",
            "P1",
            "--category",
            "feature",
            "--dedup-key",
            key,
            "--actor",
            "watchdog",
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
        print(f"Zero Factory task key: {key} (create rc={rc})")
        if output:
            print(output[-500:])
        return 0 if rc == 0 else 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

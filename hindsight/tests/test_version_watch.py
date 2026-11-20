#!/usr/bin/env python3
"""Offline tests for the Hindsight upstream version watch."""
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_versions.py"


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
        return True
    print(f"FAIL  {name}  {detail}")
    return False


def load_module(tmp):
    spec = importlib.util.spec_from_file_location("check_versions", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    dockerfile = tmp / "Dockerfile"
    dockerfile.write_text(
        "npm install @vectorize-io/hindsight-control-plane@1.2.3 && \\\n")
    versions = tmp / "versions.json"
    versions.write_text(json.dumps({"hindsight_api": "1.2.3", "control_plane": "1.2.3"}))
    setattr(mod, "DOCKERFILE", dockerfile)
    setattr(mod, "VERSIONS", versions)
    return mod


def main():
    ok = True
    ok &= check("script exists", SCRIPT.is_file())
    with tempfile.TemporaryDirectory() as td:
        mod = load_module(Path(td))
        ok &= check("parses Dockerfile pin", mod.pinned_control_plane() == "1.2.3",
                    str(mod.pinned_control_plane()))
        ok &= check("version tuples compare numerically",
                    mod.vtuple("1.2.10") > mod.vtuple("1.2.3"))

        report = mod.assess("1.2.3", "1.2.3")
        ok &= check("no drift -> no update", report["update_available"] is False, str(report))

        report = mod.assess("1.2.4", "1.2.3")
        ok &= check("API drift detected",
                    report["update_available"] and report["drift"]["api"]
                    and not report["drift"]["control_plane"], str(report))

        report = mod.assess("1.2.3", "1.2.4")
        ok &= check("control-plane drift detected",
                    report["update_available"] and report["drift"]["control_plane"]
                    and report["drift"]["pin"], str(report))

        report = mod.assess("1.2.3", "1.2.3")
        ok &= check("patch-level drift is ignored for equal versions",
                    not report["drift"]["api"] and not report["drift"]["control_plane"])

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

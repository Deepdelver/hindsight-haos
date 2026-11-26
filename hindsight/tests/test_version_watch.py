#!/usr/bin/env python3
"""Offline tests for the Hindsight upstream version watch."""

import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
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
        'pip install "hindsight-api-slim[embedded-db,local-llm,local-onnx]==1.2.3" && \\\n'
        "npm install @vectorize-io/hindsight-control-plane@1.2.3 && \\\n"
    )
    versions = tmp / "versions.json"
    versions.write_text(json.dumps({"hindsight_api": "1.2.3", "control_plane": "1.2.3"}))
    setattr(mod, "DOCKERFILE", dockerfile)
    setattr(mod, "VERSIONS", versions)
    return mod


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_fetch(pypi_version, npm_version):
    """Return a fetch_json stub that reports the given upstream versions."""

    def _fetch(url):
        if "pypi.org" in url:
            return {"info": {"version": pypi_version}}
        return {"version": npm_version}

    return _fetch


def main():
    ok = True
    ok &= check("script exists", SCRIPT.is_file())
    with tempfile.TemporaryDirectory() as td:
        mod = load_module(Path(td))
        ok &= check(
            "parses Dockerfile pin",
            mod.pinned_control_plane() == "1.2.3",
            str(mod.pinned_control_plane()),
        )
        pinned_api = getattr(mod, "pinned_api", None)

        def api_pin():
            return pinned_api() if pinned_api else None

        ok &= check(
            "parses API pin from Dockerfile",
            api_pin() == "1.2.3",
            str(api_pin()),
        )
        ok &= check(
            "version tuples compare numerically", mod.vtuple("1.2.10") > mod.vtuple("1.2.3")
        )

        report = mod.assess("1.2.3", "1.2.3")
        ok &= check("no drift -> no update", report["update_available"] is False, str(report))

        report = mod.assess("1.2.4", "1.2.3")
        ok &= check(
            "API drift detected",
            report["update_available"]
            and report["drift"]["api"]
            and not report["drift"]["control_plane"],
            str(report),
        )

        report = mod.assess("1.2.3", "1.2.4")
        ok &= check(
            "control-plane drift detected",
            report["update_available"]
            and report["drift"]["control_plane"]
            and report["drift"]["pin"],
            str(report),
        )

        report = mod.assess("1.2.3", "1.2.3")
        ok &= check(
            "equal versions produce no drift",
            not report["drift"]["api"] and not report["drift"]["control_plane"],
            str(report),
        )

        report = mod.assess("1.2.3.post1", "1.2.3")
        ok &= check(
            "build-metadata suffix does not create false drift",
            not report["update_available"],
            str(report),
        )

        # The API pin in the Dockerfile must match the API version recorded in
        # versions.json; a mismatch is what caused the historical 404 toasts.
        report = mod.assess("1.2.3", "1.2.3")
        ok &= check(
            "equal API pins produce no pin drift",
            report["drift"].get("api_pin") is False and not report["update_available"],
            str(report),
        )

        mod.VERSIONS.write_text(json.dumps({"hindsight_api": "1.2.4", "control_plane": "1.2.3"}))
        report = mod.assess("1.2.3", "1.2.3")
        ok &= check(
            "API pin mismatch detected",
            bool(report["drift"].get("api_pin")) and report["update_available"],
            str(report),
        )
        mod.VERSIONS.write_text(json.dumps({"hindsight_api": "1.2.3", "control_plane": "1.2.3"}))

        ok &= check(
            "recorded versions read from versions.json",
            mod.recorded_versions() == ("1.2.3", "1.2.3"),
            str(mod.recorded_versions()),
        )

        # Task creation must be idempotent and aimed at the right board card.
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return FakeResult(0, "created", "")

        real_run = mod.subprocess.run
        mod.subprocess.run = fake_run
        try:
            key, rc, _ = mod.create_task(
                {
                    "recorded_api": "1.2.3",
                    "recorded_control_plane": "1.2.3",
                    "pinned_control_plane": "1.2.3",
                    "pinned_api": "1.2.3",
                    "latest_api": "1.2.4",
                    "latest_control_plane": "1.2.4",
                }
            )
        finally:
            mod.subprocess.run = real_run
        ok &= check(
            "task key derived from latest upstream versions",
            key == "version-watch-1.2.4-1.2.4",
            key,
        )
        ok &= check(
            "task creation is idempotent and targeted at the hindsight-haos board",
            rc == 0
            and len(calls) == 1
            and calls[0][:5] == ["hermes", "kanban", "--board", "hindsight-haos", "create"]
            and "--board" in calls[0]
            and "hindsight-haos" in calls[0]
            and "--idempotency-key" in calls[0]
            and key in calls[0]
            and "--assignee" in calls[0]
            and "--project" in calls[0],
            str(calls),
        )

    # main() exit codes: 0 up to date, 2 drift (report only), 3 fetch failure,
    # 0 when --create-task succeeds.
    with tempfile.TemporaryDirectory() as td:
        mod2 = load_module(Path(td))
        real_fetch, real_argv, real_create = (
            getattr(mod2, "fetch_json"),
            sys.argv,
            getattr(mod2, "create_task"),
        )

        def run_main(fetch, argv, create=None):
            setattr(mod2, "fetch_json", fetch)
            sys.argv = argv
            setattr(mod2, "create_task", create or (lambda report: ("key", 0, "created")))
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                rc = mod2.main()
            return rc, buf.getvalue()

        try:
            rc, out = run_main(fake_fetch("1.2.3", "1.2.3"), ["check_versions.py"])
            ok &= check("main: up to date exits 0", rc == 0, f"rc={rc} {out}")

            drift = fake_fetch("1.2.4", "1.2.3")
            rc, out = run_main(drift, ["check_versions.py"])
            ok &= check("main: drift exits 2 without --create-task", rc == 2, f"rc={rc} {out}")

            rc, out = run_main(drift, ["check_versions.py", "--create-task"])
            ok &= check("main: --create-task exits 0 on success", rc == 0, f"rc={rc} {out}")

            def broken(url):
                raise RuntimeError("offline")

            rc, out = run_main(broken, ["check_versions.py"])
            ok &= check("main: fetch failure exits 3", rc == 3, f"rc={rc} {out}")
        finally:
            setattr(mod2, "fetch_json", real_fetch)
            sys.argv = real_argv
            setattr(mod2, "create_task", real_create)

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

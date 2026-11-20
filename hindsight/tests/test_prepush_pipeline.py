#!/usr/bin/env python3
"""Regression tests for the local pre-push assessment gate (commit 1b3ee4f).

The gate is a developer-process change rather than an add-on runtime change,
but it decides whether a push is allowed, so it needs coverage:

1. The hook exists, is executable and delegates to the pipeline script.
2. The script derives its task key from HEAD and fails closed on errors.
3. The board-detection snippet embedded in the script maps `hermes kanban
   list --json` output to done / none / status correctly.
4. End-to-end with fake `git` and `hermes` binaries: the gate allows the push
   only when the board task is `done` and the regression test exits 0.

Run: python3 hindsight/tests/test_prepush_pipeline.py
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".githooks" / "pre-push"
SCRIPT = ROOT / "scripts" / "pre-push-pipeline.sh"
REGRESSION = "python3 hindsight/tests/test_ingress_rewrite.py"

FAKE_GIT = """#!/usr/bin/env bash
if [ "$1" = rev-parse ] && [ "$2" = --show-toplevel ]; then printf '%s\\n' "$FAKE_REPO"; exit 0; fi
if [ "$1" = rev-parse ] && [ "$2" = HEAD ]; then printf '%s\\n' "TESTSHA"; exit 0; fi
exit 1
"""

FAKE_HERMES = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$HERMES_LOG"
if [ "$1" = kanban ] && [ "$2" = list ]; then
  [ -n "${FAKE_PREFIX:-}" ] && printf '%s\\n' "$FAKE_PREFIX"
  printf '%s\\n' "$FAKE_LIST_JSON"
  exit 0
fi
if [ "$1" = kanban ] && [ "$2" = create ]; then exit 0; fi
exit 1
"""


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
        return True
    print(f"FAIL  {name}  {detail}")
    return False


def make_exec(path, text):
    path.write_text(text)
    path.chmod(0o755)


def clean_env(extra):
    env = dict(os.environ)
    # A spawned worker context fences the real board; the fakes below do not
    # touch the real board, but drop the marker so nothing is accidentally gated.
    env.pop("HERMES_DELEGATED_CHILD_CONTEXT", None)
    bindir = extra.pop("_BINDIR")
    env.update(extra)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    return env


def detection_snippet():
    text = SCRIPT.read_text()
    match = re.search(r"python3 - <<'PY'\n(.*?)\nPY", text, re.S)
    return match.group(1) if match else None


def run_detection(list_json, prefix=""):
    """Run the exact detection code embedded in the pipeline script."""
    snippet = detection_snippet()
    if snippet is None:
        return "<no-snippet>"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bindir = td / "bin"
        bindir.mkdir()
        make_exec(bindir / "hermes", FAKE_HERMES)
        detector = td / "detect.py"
        detector.write_text(snippet)
        env = clean_env({
            "KEY": "prepush-TESTSHA",
            "BOARD": "hindsight-haos",
            "FAKE_LIST_JSON": list_json,
            "FAKE_PREFIX": prefix,
            "HERMES_LOG": str(td / "hermes.log"),
            "_BINDIR": bindir,
        })
        # The detection snippet prints a warning line itself, ignore stderr.
        result = subprocess.run(["python3", str(detector)], capture_output=True,
                                text=True, env=env)
        lines = result.stdout.strip().splitlines()
        return lines[-1].strip() if lines else f"<no output: {result.stderr.strip()}>"


def run_gate(list_json, regression_exit=0):
    """Run the whole gate with fake git/hermes and a stub regression test."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bindir = td / "bin"
        bindir.mkdir()
        repo = td / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "hindsight" / "tests").mkdir(parents=True)
        shutil.copy(SCRIPT, repo / "scripts" / SCRIPT.name)
        marker = td / "regression-ran"
        (repo / "hindsight" / "tests" / "test_ingress_rewrite.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('ran')\n"
            f"raise SystemExit({regression_exit})\n"
        )
        make_exec(bindir / "git", FAKE_GIT)
        log = td / "hermes.log"
        make_exec(bindir / "hermes", FAKE_HERMES)
        env = clean_env({
            "FAKE_REPO": str(repo),
            "FAKE_LIST_JSON": list_json,
            "HERMES_LOG": str(log),
            "_BINDIR": bindir,
        })
        result = subprocess.run(["bash", str(repo / "scripts" / SCRIPT.name)],
                                cwd=str(repo), capture_output=True, text=True,
                                env=env, input="")
        log_text = log.read_text() if log.exists() else ""
        return result.returncode, marker.exists(), log_text


def main():
    ok = True

    # --- 1. Structural checks -------------------------------------------------
    ok &= check("pre-push hook exists", HOOK.is_file())
    ok &= check("pre-push hook is executable", HOOK.is_file() and os.access(HOOK, os.X_OK))
    hook = HOOK.read_text() if HOOK.is_file() else ""
    ok &= check("hook delegates to pipeline script", "scripts/pre-push-pipeline.sh" in hook)
    ok &= check("pipeline script exists", SCRIPT.is_file())
    ok &= check("pipeline script is executable", SCRIPT.is_file() and os.access(SCRIPT, os.X_OK))
    script = SCRIPT.read_text() if SCRIPT.is_file() else ""
    ok &= check("script fails closed (set -euo pipefail)", "set -euo pipefail" in script)
    ok &= check("key is derived from HEAD", 'KEY="prepush-${SHA}"' in script)
    ok &= check("SHA comes from git rev-parse HEAD", 'SHA="$(git rev-parse HEAD)"' in script)
    ok &= check("done branch runs regression test", REGRESSION in script)
    ok &= check("task creation uses the commit key", '--idempotency-key "$KEY"' in script)
    ok &= check("gate has done/none/default branches",
                all(branch in script for branch in ("done)", "none)", "*)")))

    # --- 2. Board detection snippet -----------------------------------------
    done_json = '[{"idempotency_key":"prepush-TESTSHA","status":"done"}]'
    running_json = '[{"idempotency_key":"prepush-TESTSHA","status":"running"}]'
    body_json = '[{"body":"Pre-push gate for commit X (key prepush-TESTSHA).","status":"done"}]'
    ok &= check("detection: no task -> none", run_detection("[]") == "none",
                run_detection("[]"))
    ok &= check("detection: done task -> done", run_detection(done_json) == "done",
                run_detection(done_json))
    ok &= check("detection: running task -> running", run_detection(running_json) == "running",
                run_detection(running_json))
    ok &= check("detection: body containing key also matches",
                run_detection(body_json) == "done", run_detection(body_json))
    ok &= check("detection: tolerates a warning line before JSON",
                run_detection(done_json, prefix="hermes startup warning") == "done",
                run_detection(done_json, prefix="hermes startup warning"))

    # --- 3. End-to-end gate --------------------------------------------------
    rc, ran, log = run_gate(done_json)
    ok &= check("gate allows push when task done and test passes",
                rc == 0 and ran and "create" not in log, f"rc={rc} ran={ran} log={log!r}")

    rc, ran, log = run_gate("[]")
    ok &= check("gate creates keyed task and blocks push when none exists",
                rc != 0 and not ran and "create" in log and "prepush-TESTSHA" in log,
                f"rc={rc} ran={ran} log={log!r}")

    rc, ran, log = run_gate(running_json)
    ok &= check("gate blocks push while assessment is running",
                rc != 0 and not ran and "create" not in log,
                f"rc={rc} ran={ran} log={log!r}")

    rc, ran, log = run_gate(done_json, regression_exit=1)
    ok &= check("gate blocks push when regression test fails",
                rc != 0 and ran, f"rc={rc} ran={ran}")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

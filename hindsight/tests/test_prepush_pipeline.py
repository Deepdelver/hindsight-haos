#!/usr/bin/env python3
"""Regression tests for the pre-push assessment gate.

Covers:
1. Hook, dispatcher and script wiring and fail-closed behaviour.
2. Key derivation: the first unpushed commit without a `Pipeline-Key:` trailer,
   covering real multi-line git bodies and the all-pipeline-commits fallback.
3. Board detection: done / none / running / malformed prefix.
4. End-to-end with fake git/hermes: push allowed only when the task is done and
   both regression suites exit 0.

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
SETUP = ROOT / "scripts" / "setup-hooks.sh"
REGRESSIONS = [
    "python3 hindsight/tests/test_ingress_rewrite.py",
    "python3 hindsight/tests/test_prepush_pipeline.py",
]

FAKE_GIT = """#!/usr/bin/env bash
if [ "$1" = rev-parse ] && [ "$2" = --show-toplevel ]; then printf '%s\\n' "$FAKE_REPO"; exit 0; fi
if [ "$1" = rev-parse ] && [ "$2" = HEAD ]; then printf '%s\\n' "HEADSHA"; exit 0; fi
if [ "$1" = rev-parse ] && [ "$2" = origin/main ]; then printf '%s\\n' "BASESHA"; exit 0; fi
if [ "$1" = log ]; then printf '%b' "${FAKE_GIT_LOG:-@@KEY@@LATERSHA\\tassessment docs\\n\\nPipeline-Key: KEYSHA\\n\\n@@KEY@@KEYSHA\\tstart work\\n\\n}"; exit 0; fi
if [ "$1" = remote ] && [ "$2" = get-url ]; then printf '%s\\n' "${FAKE_REMOTE:-}"; exit 0; fi
if [ "$1" = -C ] && [ "$3" = remote ] && [ "$4" = get-url ]; then printf '%s\\n' "${FAKE_REMOTE:-}"; exit 0; fi
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
            "KEY": "prepush-KEYSHA",
            "BOARD": "hindsight-haos",
            "FAKE_LIST_JSON": list_json,
            "FAKE_PREFIX": prefix,
            "HERMES_LOG": str(td / "hermes.log"),
            "_BINDIR": bindir,
        })
        result = subprocess.run(["python3", str(detector)], capture_output=True,
                                text=True, env=env)
        lines = result.stdout.strip().splitlines()
        return lines[-1].strip() if lines else f"<no output: {result.stderr.strip()}>"


def stage_repo(td, script=SCRIPT):
    bindir = td / "bin"
    bindir.mkdir(exist_ok=True)
    repo = td / "repo"
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "hindsight" / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy(script, repo / "scripts" / script.name)
    make_exec(bindir / "git", FAKE_GIT)
    make_exec(bindir / "hermes", FAKE_HERMES)
    return bindir, repo


def run_gate(list_json, regression_exit=0, git_log=None):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bindir, repo = stage_repo(td)
        marker = td / "regression-ran"
        for name in ("test_ingress_rewrite.py", "test_prepush_pipeline.py"):
            (repo / "hindsight" / "tests" / name).write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('ran')\n"
                f"raise SystemExit({regression_exit})\n"
            )
        log = td / "hermes.log"
        env = clean_env({
            "FAKE_REPO": str(repo),
            "FAKE_LIST_JSON": list_json,
            "HERMES_LOG": str(log),
            "_BINDIR": bindir,
        })
        if git_log is not None:
            env["FAKE_GIT_LOG"] = git_log
        result = subprocess.run(["bash", str(repo / "scripts" / SCRIPT.name)],
                                cwd=str(repo), capture_output=True, text=True,
                                env=env, input="")
        log_text = log.read_text() if log.exists() else ""
        return result.returncode, marker.exists(), log_text


def run_gate_without_hermes():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bindir, repo = stage_repo(td)
        for tool in ("python3", "bash", "env"):
            real = shutil.which(tool)
            if real:
                (bindir / tool).symlink_to(real)
        bash = shutil.which("bash") or "/bin/bash"
        env = {"PATH": str(bindir), "FAKE_REPO": str(repo)}
        result = subprocess.run(
            [bash, str(repo / "scripts" / SCRIPT.name)],
            cwd=str(repo), capture_output=True, text=True, env=env, input="")
        return result.returncode, result.stderr


def run_dispatcher(remote):
    """The global dispatcher must only gate hindsight-haos repositories."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bindir, repo = stage_repo(td)
        script = repo / "scripts" / "pre-push-pipeline.sh"
        marker = td / "gated"
        script.write_text(f"#!/usr/bin/env bash\ntouch {str(marker)!r}\n")
        script.chmod(0o755)
        setup = SETUP.read_text()
        dispatch = re.search(r"cat > \"\$HOOKDIR/pre-push\" <<'DISPATCH'\n(.*?)\nDISPATCH", setup, re.S)
        if not dispatch:
            return None
        dispatcher = td / "dispatch"
        make_exec(dispatcher, dispatch.group(1))
        env = clean_env({"FAKE_REPO": str(repo), "FAKE_REMOTE": remote, "_BINDIR": bindir})
        subprocess.run(["bash", str(dispatcher)], cwd=str(repo),
                       capture_output=True, text=True, env=env, input="")
        return marker.exists()


def main():
    ok = True
    script = SCRIPT.read_text() if SCRIPT.is_file() else ""

    # --- 1. Structural checks -------------------------------------------------
    ok &= check("pre-push hook exists", HOOK.is_file())
    ok &= check("pre-push hook is executable", HOOK.is_file() and os.access(HOOK, os.X_OK))
    hook = HOOK.read_text() if HOOK.is_file() else ""
    ok &= check("hook delegates to pipeline script", "scripts/pre-push-pipeline.sh" in hook)
    ok &= check("pipeline script exists", SCRIPT.is_file())
    ok &= check("pipeline script is executable", SCRIPT.is_file() and os.access(SCRIPT, os.X_OK))
    ok &= check("setup script exists", SETUP.is_file())
    ok &= check("manual .pipeline-id is gone", not (ROOT / ".pipeline-id").exists())
    ok &= check("script fails closed (set -euo pipefail)", "set -euo pipefail" in script)
    ok &= check("key comes from unpushed commits", "git log --format" in script)
    ok &= check("key derivation groups multi-line commit bodies", "@@KEY@@%H%x09%B" in script)
    ok &= check("pipeline commits are skipped via trailer", "Pipeline-Key:" in script)
    ok &= check("HEAD is reported for context", 'SHA="$(git rev-parse HEAD)"' in script)
    for regression in REGRESSIONS:
        ok &= check(f"done branch runs {regression}", regression in script)
    ok &= check("task creation uses derived key", '--idempotency-key "$KEY"' in script)
    ok &= check("gate has done/none/default branches",
                all(branch in script for branch in ("done)", "none)", "*)")))

    # --- 2. Board detection ---------------------------------------------------
    done_json = '[{"idempotency_key":"prepush-KEYSHA","status":"done"}]'
    running_json = '[{"idempotency_key":"prepush-KEYSHA","status":"running"}]'
    body_json = '[{"body":"Pre-push gate for commit X (key prepush-KEYSHA).","status":"done"}]'
    ok &= check("detection: no task -> none", run_detection("[]") == "none", run_detection("[]"))
    ok &= check("detection: done task -> done", run_detection(done_json) == "done", run_detection(done_json))
    ok &= check("detection: running task -> running", run_detection(running_json) == "running", run_detection(running_json))
    ok &= check("detection: body containing key also matches", run_detection(body_json) == "done", run_detection(body_json))
    ok &= check("detection: tolerates a warning line before JSON",
                run_detection(done_json, prefix="hermes startup warning") == "done",
                run_detection(done_json, prefix="hermes startup warning"))

    # --- 3. End-to-end gate ---------------------------------------------------
    rc, ran, log = run_gate(done_json)
    ok &= check("gate allows push when task done and tests pass",
                rc == 0 and ran and "create" not in log, f"rc={rc} ran={ran} log={log!r}")
    rc, ran, log = run_gate("[]")
    ok &= check("gate creates keyed task and blocks push when none exists",
                rc != 0 and not ran and "create" in log and "prepush-KEYSHA" in log,
                f"rc={rc} ran={ran} log={log!r}")
    rc, ran, log = run_gate(running_json)
    ok &= check("gate blocks push while assessment is running",
                rc != 0 and not ran and "create" not in log, f"rc={rc} ran={ran} log={log!r}")
    rc, ran, log = run_gate(done_json, regression_exit=1)
    ok &= check("gate blocks push when regression test fails", rc != 0 and ran, f"rc={rc} ran={ran}")
    rc, err = run_gate_without_hermes()
    ok &= check("gate fails closed when hermes CLI is missing", rc != 0, f"rc={rc} err={err!r}")

    # --- 3b. Key derivation with real, multi-line git bodies ------------------
    # `git log --format=%B` puts a trailer on its own line. The default fake log
    # above models that (newest assessment commit with a trailer, older
    # change-set start without one); the create path echoes the derived key.
    rc, ran, log = run_gate("[]")
    ok &= check("key skips pipeline commit, uses change-set start",
                rc != 0 and "prepush-KEYSHA" in log and "prepush-LATERSHA" not in log,
                f"log={log!r}")

    sole = r"@@KEY@@KEYSHA\tstart work\n\n"
    rc, ran, log = run_gate("[]", git_log=sole)
    ok &= check("key uses sole unpushed commit",
                rc != 0 and "prepush-KEYSHA" in log, f"log={log!r}")

    all_trailers = (r"@@KEY@@LATERSHA\tassessment docs\n\nPipeline-Key: KEYSHA\n\n"
                    r"@@KEY@@KEYSHA\tstart work\n\nPipeline-Key: OLDER\n\n")
    rc, ran, log = run_gate("[]", git_log=all_trailers)
    ok &= check("key falls back to HEAD when all commits have trailers",
                rc != 0 and "prepush-HEADSHA" in log, f"log={log!r}")

    # --- 4. Global dispatcher -------------------------------------------------
    ok &= check("dispatcher gates hindsight-haos repos",
                run_dispatcher("https://github.com/Deepdelver/hindsight-haos.git") is True)
    ok &= check("dispatcher ignores other repos",
                run_dispatcher("https://github.com/other/repo.git") is False)

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

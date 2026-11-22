#!/usr/bin/env bash
# Agent assessment pipeline gate for GitHub pushes.
#
# Every push must be preceded by a Kanban task on this project's board that
# assesses the changes and brings README/DOCS and tests up to date. The task
# is keyed to the first commit of the change set (a commit without a
# `Pipeline-Key:` trailer), so commits produced by the assessment itself do
# not start a new task.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
SHA="$(git rev-parse HEAD)"
BOARD="hindsight-haos"
PROJECT="hindsight-haos"

# Determine the change-set key from commits not yet pushed. Pipeline commits
# carry a Pipeline-Key trailer and are skipped. `%B` is multi-line: a trailer
# sits on its own line, never on the subject line that follows the SHA. Group
# lines into commit records with a marker and inspect each whole message,
# otherwise the newest assessment commit would be mistaken for the key.
BASE="$(git rev-parse origin/main 2>/dev/null || true)"
KEY_SHA=""
if [ -n "$BASE" ]; then
  KEY_SHA="$(git log --format='@@KEY@@%H%x09%B' "$BASE..HEAD" | awk '
    /^@@KEY@@/ {
      if (have && !trailer) { print sha; done = 1; exit }
      split($0, rec, "\t"); sha = substr(rec[1], 8); trailer = 0; have = 1
    }
    /Pipeline-Key:/ { trailer = 1 }
    END { if (!done && have && !trailer) print sha }
  ')"
fi
[ -n "$KEY_SHA" ] || KEY_SHA="$SHA"
KEY="prepush-${KEY_SHA}"

# Read the status of the pipeline task for this change set from the board.
STATUS="$(BOARD="$BOARD" KEY="$KEY" python3 - <<'PY'
import json, os, subprocess
key = os.environ["KEY"]
out = subprocess.run(["hermes", "kanban", "list", "--json"],
                     capture_output=True, text=True).stdout
start = out.find("[")
if start < 0:
    print("none")
    raise SystemExit
try:
    tasks = json.loads(out[start:])
except Exception:
    print("none")
    raise SystemExit
for t in tasks:
    if key in (t.get("body") or "") or t.get("idempotency_key") == key:
        print(t.get("status", "unknown"))
        break
else:
    print("none")
PY
)"

case "$STATUS" in
  done)
    echo "Pipeline task for change set $KEY_SHA is done. Running regression tests before push..."
    python3 hindsight/tests/test_source_defaults.py
    python3 hindsight/tests/test_ingress_rewrite.py
    python3 hindsight/tests/test_prepush_pipeline.py
    python3 hindsight/tests/test_version_watch.py
    echo "Push allowed."
    exit 0
    ;;
  none)
    echo "No assessment pipeline for change set $KEY_SHA. Creating one on board '$BOARD'..."
    hermes kanban create \
      "Pre-push assessment: review changes, update docs and tests" \
      --project "$PROJECT" \
      --assignee default \
      --workspace "dir:$REPO" \
      --idempotency-key "$KEY" \
      --goal \
      --body-file - <<EOF 2>&1 | tail -8
Pre-push gate for change set starting at $KEY_SHA (HEAD $SHA, key $KEY).

Assess the changes in this repository ($REPO) and finish these items before any push:

1. Assessment: review commits/diff since origin/main and identify behaviour changes, new/removed options, ports, config keys and defaults. Note any risk or regression.
2. Docs: make sure README.md and hindsight/DOCS.md describe the current behaviour, features, ports, configuration and troubleshooting. Update them if anything is missing or stale.
3. Tests: make sure hindsight/tests/ covers changed behaviour. Add or update tests, then run:
   python3 hindsight/tests/test_ingress_rewrite.py
   python3 hindsight/tests/test_prepush_pipeline.py
   python3 hindsight/tests/test_version_watch.py
4. Report: list files changed, the exact test commands and their results, and any residual risk.

Do NOT commit and do NOT push. Leave any README/DOCS/test edits uncommitted in
the working tree. The parent commits them with this trailer:

    Pipeline-Key: $KEY_SHA

That trailer keeps the change-set key stable, so the push will be allowed.
EOF
    echo "Pipeline triggered. Re-run the push after the task is completed."
    exit 1
    ;;
  *)
    echo "Assessment pipeline for change set $KEY_SHA is still '$STATUS'. Wait for it to finish, then re-run the push."
    exit 1
    ;;
esac

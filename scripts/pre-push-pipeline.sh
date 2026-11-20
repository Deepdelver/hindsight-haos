#!/usr/bin/env bash
# Agent assessment pipeline gate for GitHub pushes.
#
# Every push must be preceded by a Kanban task on this project's board that
# assesses the changes and brings README/DOCS and tests up to date. The task
# is keyed to the exact commit being pushed, so a re-run after completion is
# allowed and a new commit starts a fresh assessment.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
SHA="$(git rev-parse HEAD)"
KEY="prepush-${SHA}"
BOARD="hindsight-haos"
PROJECT="hindsight-haos"

# Read the status of the pipeline task for this commit from the board.
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
    echo "Pipeline task for $SHA is done. Running regression tests before push..."
    python3 hindsight/tests/test_ingress_rewrite.py
    echo "Push allowed."
    exit 0
    ;;
  none)
    echo "No assessment pipeline for $SHA. Creating one on board '$BOARD'..."
    hermes kanban create \
      "Pre-push assessment: review changes, update docs and tests" \
      --project "$PROJECT" \
      --assignee default \
      --workspace "dir:$REPO" \
      --idempotency-key "$KEY" \
      --goal \
      --body-file - <<EOF 2>&1 | tail -8
Pre-push gate for commit $SHA (key $KEY).

Assess the changes in this repository ($REPO) and finish these items before any push:

1. Assessment: review commits/diff since origin/main and identify behaviour changes, new/removed options, ports, config keys and defaults. Note any risk or regression.
2. Docs: make sure README.md and hindsight/DOCS.md describe the current behaviour, features, ports, configuration and troubleshooting. Update them if anything is missing or stale.
3. Tests: make sure hindsight/tests/ covers changed behaviour. Add or update tests, then run:
   python3 hindsight/tests/test_ingress_rewrite.py
4. Report: list files changed, the exact test command and its result, and any residual risk.

Do NOT commit and do NOT push. Leave any README/DOCS/test edits uncommitted in
the working tree so the pre-push key for this commit stays valid. The parent
session commits and pushes after this task is done.
EOF
    echo "Pipeline triggered. Re-run the push after the task is completed."
    exit 1
    ;;
  *)
    echo "Assessment pipeline for $SHA is still '$STATUS'. Wait for it to finish, then re-run the push."
    exit 1
    ;;
esac

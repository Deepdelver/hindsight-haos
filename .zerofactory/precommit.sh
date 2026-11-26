#!/usr/bin/env bash
# Zero Factory precommit gate for deepdelver-hindsight-haos.
#
# Phases follow the tooling this repository already uses:
#   format -> ruff (ruff.toml); no other Python formatter is configured
#   build  -> python3 -m compileall -q . (there is no package/build manifest)
#   test   -> the five standalone regression suites also run by
#            scripts/pre-push-pipeline.sh and .github/workflows/regression-tests.yml
#            (stdlib only: no pytest stack to install)
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# install-hook links this script into .git/hooks. When Git runs that hook,
# BASH_SOURCE[0] is the *hook* path, so the naive dirname above resolves to
# .git/ (or the custom hooks dir) rather than the repository root. Resolve the
# symlink chain and derive ROOT_DIR from the real script location instead.
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  SOURCE_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE_LINK="$(readlink "$SOURCE")"
  case "$SOURCE_LINK" in
  /*) SOURCE="$SOURCE_LINK" ;;
  *) SOURCE="$SOURCE_DIR/$SOURCE_LINK" ;;
  esac
done
ROOT_DIR="$(cd "$(dirname "$SOURCE")/.." && pwd)"
cd "$ROOT_DIR"

# `uv tool install` and `pip --user` put executables here.
export PATH="$HOME/.local/bin:$PATH"

REGRESSION_SUITES=(
  "hindsight/tests/test_source_defaults.py"
  "hindsight/tests/test_ingress_rewrite.py"
  "hindsight/tests/test_prepush_pipeline.py"
  "hindsight/tests/test_version_watch.py"
  "hindsight/tests/test_continit_providers.py"
  "hindsight/tests/test_setup_gh_issues.py"
)

ensure_ruff() {
  if command -v ruff >/dev/null 2>&1; then
    return 0
  fi
  echo "→ ruff not found; installing pinned formatter"
  if command -v uv >/dev/null 2>&1; then
    uv tool install 'ruff==0.17.6' >/dev/null 2>&1 || true
  fi
  if ! command -v ruff >/dev/null 2>&1; then
    python3 -m pip install --user 'ruff==0.17.6' >/dev/null 2>&1 || true
  fi
  if ! command -v ruff >/dev/null 2>&1; then
    echo "ERROR: could not install ruff. Install it with: uv tool install 'ruff==0.17.6'" >&2
    exit 1
  fi
}

run_format() {
  echo "→ format: ruff check --fix . && ruff format ."
  ensure_ruff
  ruff check --fix .
  ruff format .
}

run_build() {
  echo "→ build: python3 -m compileall -q ."
  python3 -m compileall -q .
}

run_test() {
  echo "→ test: standalone regression suites (stdlib only)"
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is not on PATH; install Python 3 and retry." >&2
    exit 1
  fi
  # Every suite documents itself as third-party-free. Verify that contract
  # rather than silently degrading to a different runner or an empty suite.
  if ! python3 -c 'import contextlib, importlib.util, json, pathlib, re, subprocess, sys, tempfile' >/dev/null 2>&1; then
    echo "ERROR: python3 stdlib is incomplete; reinstall Python 3." >&2
    exit 1
  fi
  for suite in "${REGRESSION_SUITES[@]}"; do
    if [ ! -f "$suite" ]; then
      echo "ERROR: missing regression suite $suite" >&2
      exit 1
    fi
    echo "  - python3 $suite"
    python3 "$suite"
  done
}

install_hook() {
  HOOK_DIR="$(git rev-parse --git-path hooks 2>/dev/null || echo ".git/hooks")"
  mkdir -p "$HOOK_DIR"
  # In the standard <root>/.git/hooks layout, ../.. reaches the repository
  # root. Custom/absolute core.hooksPath values need a computed target.
  case "$HOOK_DIR" in
  ".git/hooks" | "$ROOT_DIR/.git/hooks")
    ln -sf "../../.zerofactory/precommit.sh" "$HOOK_DIR/pre-commit"
    ;;
  *)
    TARGET="$(realpath --relative-to="$HOOK_DIR" "$ROOT_DIR/.zerofactory/precommit.sh" 2>/dev/null || echo "$ROOT_DIR/.zerofactory/precommit.sh")"
    ln -sf "$TARGET" "$HOOK_DIR/pre-commit"
    ;;
  esac
  chmod +x "$HOOK_DIR/pre-commit"
  echo "✓ Linked .zerofactory/precommit.sh -> $HOOK_DIR/pre-commit"
}

case "${1:-all}" in
format) run_format ;;
build) run_build ;;
test) run_test ;;
install-hook) install_hook ;;
all | *)
  run_format
  run_build
  run_test
  ;;
esac

echo "✓ Zero Factory precommit checks passed!"

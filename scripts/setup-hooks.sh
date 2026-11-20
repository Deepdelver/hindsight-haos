#!/usr/bin/env bash
# Install the pre-push assessment gate once, for all clones on this machine.
#
# Usage: scripts/setup-hooks.sh [global|local]
#   global (default): write a dispatcher to ~/.hermes/git-hooks and set
#                     core.hooksPath globally. It only gates repositories
#                     whose origin URL contains "hindsight-haos".
#   local:            set core.hooksPath .githooks in the current clone only.
set -euo pipefail

MODE="${1:-global}"
REPO="$(git rev-parse --show-toplevel)"

if [ "$MODE" = "local" ]; then
  git -C "$REPO" config core.hooksPath .githooks
  echo "Local hook installed in $REPO"
  exit 0
fi

HOOKDIR="${HOME}/.hermes/git-hooks"
mkdir -p "$HOOKDIR"
cat > "$HOOKDIR/pre-push" <<'DISPATCH'
#!/usr/bin/env bash
# Global pre-push dispatcher: gate only the hindsight-haos repository.
repo="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$repo" ] || exit 0
remote="$(git -C "$repo" remote get-url origin 2>/dev/null || true)"
case "$remote" in
  *hindsight-haos*)
    exec "$repo/scripts/pre-push-pipeline.sh"
    ;;
  *)
    exit 0
    ;;
esac
DISPATCH
chmod +x "$HOOKDIR/pre-push"
git config --global core.hooksPath "$HOOKDIR"
echo "Global hook installed at $HOOKDIR/pre-push"
echo "Only repositories with 'hindsight-haos' in their origin URL are gated."

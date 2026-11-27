# Pre-push assessment — prepush-f9c3bd1afd00901c6e9188995fbf5db498fcd94c
Worktree: /config/.zerofactory/workspaces/deepdelver-hindsight-haos/worktrees/zf-dhh-96833dcd/deepdelver-hindsight-haos
HEAD: f9c3bd1afd00901c6e9188995fbf5db498fcd94c
Status: DONE (no commit, no push — edits left uncommitted in the working tree)

## Files changed (13)
Added:
  .github/ISSUE_TEMPLATE/bug_report.yml
  .github/ISSUE_TEMPLATE/config.yml
  .github/ISSUE_TEMPLATE/feature_request.yml
  hindsight/tests/test_setup_gh_issues.py
  scripts/setup_gh_issues.py
Modified:
  .github/workflows/regression-tests.yml
  .zerofactory/precommit.sh
  README.md
  hindsight/tests/test_prepush_pipeline.py
  hindsight/tests/test_source_defaults.py
  hindsight/tests/test_version_watch.py
  scripts/check_versions.py
  scripts/pre-push-pipeline.sh

## Assessment
Change set adds a 6th regression suite (test_setup_gh_issues.py) covering the vendored
GitHub issue-template + labels generator, and unifies pipeline references from "five" to
"six".

Behaviour changes:
- test_setup_gh_issues.py (new): issue templates carry the zerofactory label; blank issues
  disabled; labels (zerofactory, bug, feature, p0-3) provisioned via gh. Run via
  scripts/setup_gh_issues.py --path . --align.
- scripts/setup_gh_issues.py (new): vendored generator, align/non-align semantics, repo-aware
  config, git-remote detection.
- test_source_defaults.py: added release_metadata_errors() — versions.json components must
  agree, Dockerfile pins must match, config.yaml version must be a quoted string.
- test_version_watch.py: zerofactory task-creation expectation updated to the new
  hermes zerofactory create flag shape.

No addon ports/options/config keys changed. Repo-level CI/pipeline config only.

## Docs
- README.md — updated to "six regression suites" (3 places), test_setup_gh_issues.py added to
  the test-command list, new "GitHub issues and Zero Factory triage" section. No stale "five".
- hindsight/DOCS.md — addon doc; not touched by this change set; complete and current
  (Setup, Configuration options, Ports 9999/9997, Data, Version compatibility, Troubleshooting).

## Tests — all six suites PASS (exit 0)
1. python3 hindsight/tests/test_source_defaults.py
2. python3 hindsight/tests/test_ingress_rewrite.py
3. python3 hindsight/tests/test_prepush_pipeline.py
4. python3 hindsight/tests/test_version_watch.py
5. python3 hindsight/tests/test_continit_providers.py
6. python3 hindsight/tests/test_setup_gh_issues.py

## Residual risk
- No functional risk. All six suites passed.
- hindsight/tests/test_prepush_pipeline.py is unmerged in the index (UU, 3 stages) with the
  docstring resolved to "six". Must be git add'd before the parent commit; intentionally not
  committed here.

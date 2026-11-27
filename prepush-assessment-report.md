# Pre-push assessment — prepush-9a0965f8d42b4c657bb8855c378cedc3fd457514

Worktree: /config/.zerofactory/workspaces/deepdelver-hindsight-haos/worktrees/zf-dhh-96833dcd/deepdelver-hindsight-haos
Task key (from task body): prepush-9a0965f8d42b4c657bb8855c378cedc3fd457514
HEAD assessed: 8c5f9e1b4c7b0ce2f1cdfdecf3c496dec3ee2bfd (one commit after the key commit)
Base: origin/main b104f8fc26082df8f6c70a56e3be0cb4828eeae5 (also the merge base)
Status: DONE — no commit, no push; documentation and test edits left uncommitted in the working tree for the parent to commit.

## 1. Assessment

Unpushed commits: f9c3bd1 (drift guard), 1095992 (merge conflict resolution),
9a0965f (merge of origin/main, change-set key), 8c5f9e1 (assessment report).

Net diff `origin/main...HEAD`:

- Modified: `hindsight/tests/test_prepush_pipeline.py` (+103) — adds a suite-list
  drift guard across the five pipeline locations that spell out the regression
  suites, with self-checks that reject a missing suite and a mistyped path.
- Added: `prepush-assessment-report.md` (+59) — this report (rewritten here with
  the current key, HEAD, docs status, test results and residual risks).

Behaviour changes:

- No add-on runtime code changed. Ports (8888 API/MCP, 9999 direct UI, 9997
  ingress), configuration options, defaults and config.yaml version (1.2.28)
  are unchanged in this change set. Upstream pins remain 1.3.0/1.3.0.
- The sixth suite (`test_setup_gh_issues.py`), its generator, issue templates and
  the workflow are already on `origin/main` (b104f8f); this branch only aligns
  the suite lists and guards them against future drift.
- Working-tree edits left for the parent: `hindsight/DOCS.md` (stale "five
  suites" corrected to six) and `hindsight/tests/test_prepush_pipeline.py`
  (guard extended so README.md and DOCS.md must name all six suites). These were
  made by a concurrent assessment worker in the shared worktree and left intact.

Risk/regression: low — test/CI plumbing and docs only, no production paths. The
drift guard is self-checked, so it fails when a suite is dropped or mistyped.

## 2. Docs

- `README.md`: already current — six regression suites, six test commands,
  GitHub issues / Zero Factory triage section, ports 8888/9999/9997, all config
  options including `consolidation_max_completion_tokens` (default 8192). No edit needed.
- `hindsight/DOCS.md`: was stale in the pre-push troubleshooting bullet ("all
  five regression suites" and five names). Fixed in the working tree to six
  names including `test_setup_gh_issues.py`; the rest of the file matches
  `config.yaml` and the 1.3.0 pins.

## 3. Tests — exact commands and results

All commands were run from the worktree root; each exited 0.

| Command | Exit | PASS checks |
| --- | --- | --- |
| `python3 hindsight/tests/test_source_defaults.py` | 0 | 2 |
| `python3 hindsight/tests/test_ingress_rewrite.py` | 0 | 18 |
| `python3 hindsight/tests/test_prepush_pipeline.py` | 0 | 82 |
| `python3 hindsight/tests/test_version_watch.py` | 0 | 20 |
| `python3 hindsight/tests/test_continit_providers.py` | 0 | 48 |
| `python3 hindsight/tests/test_setup_gh_issues.py` | 0 | 51 |

`test_source_defaults.py` prints a summary line instead of `RESULT: PASS`; all
other suites ended with `RESULT: PASS`. No failures.

## 4. Residual risk

1. **Change-set key drift — parent action required.** The key derivation in
   `scripts/pre-push-pipeline.sh` (newest unpushed commit without a
   `Pipeline-Key:` trailer) currently resolves to
   `prepush-8c5f9e1b4c7b0ce2f1cdfdecf3c496dec3ee2bfd`, not the task's
   `prepush-9a0965f...`: commit 8c5f9e1 was created after the task and has no
   trailer. Adding a trailer only to the parent's new commit will NOT fix this —
   the derivation will still stop at 8c5f9e1. The parent must amend/rebase
   8c5f9e1 so it carries `Pipeline-Key: 9a0965f8d42b4c657bb8855c378cedc3fd457514`,
   or complete a separate assessment task keyed to 8c5f9e1. Otherwise the push
   hook creates a new task and blocks the push again.
2. **Concurrent edits in a shared `dir` worktree.** Sibling assessment workers
   modified `hindsight/DOCS.md` and `hindsight/tests/test_prepush_pipeline.py`
   while this assessment was running. Their edits were preserved, not
   overwritten; serialize the workers (or use separate worktrees) before the
   parent commit to avoid lost updates. Flagged on the board.
3. No runtime/add-on behaviour risk identified in the net diff.

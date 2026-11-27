# Pre-push assessment — prepush-ece03d6cca7db790680412ae01abc161ba548b56

Worktree: /config/.zerofactory/workspaces/deepdelver-hindsight-haos/worktrees/zf-dhh-96833dcd/deepdelver-hindsight-haos
Task key (from task body): prepush-ece03d6cca7db790680412ae01abc161ba548b56
HEAD assessed: ece03d6cca7db790680412ae01abc161ba548b56
Base: origin/main 63e7cb381f9ec4672c385f78e08d2c71217c71b3 (change-set merge base b104f8f)

## 1. Assessment

Unpushed commits on origin/main..HEAD (5):

- f9c3bd1 test: guard the five-suite list against drift (Ponytail Rung 2)
- 1095992 fix(merge): resolve merge conflicts with main
- 9a0965f Merge branch 'origin/main' into task branch
- 8c5f9e1 test: guard the five-suite list against drift (Ponytail Rung 2)
- ece03d6 test: guard the five-suite list against drift (Ponytail Rung 2)  <- HEAD

Net diff `origin/main...HEAD`: 3 files changed (+205/-2):

- `hindsight/tests/test_prepush_pipeline.py` (+122) — adds a suite-list drift
  guard across the five pipeline locations that spell out the regression
  suites (precommit REGRESSION_SUITES, pre-push done branch, pre-push task
  body, GitHub workflow, version-watch task body), with self-checks that reject
  a missing suite and a mistyped path. Also extended so README.md and
  hindsight/DOCS.md must name all six suites.
- `hindsight/DOCS.md` — pre-push troubleshooting bullet corrected: "all five
  regression suites" → "all six", and all six suite names listed.
- `prepush-assessment-report.md` (+81) — this report.

Behaviour changes:

- No add-on runtime code changed. Ports (8888 API/MCP, 9999 direct UI, 9997
  internal ingress), configuration options, defaults and config.yaml version
  (1.2.28) are unchanged in this change set. Upstream pins remain 1.3.0/1.3.0.
  Consolidation defaults (consolidation_max_completion_tokens → 8192) are
  unchanged.
- The sixth suite (`test_setup_gh_issues.py`), its generator, issue templates
  and the GitHub workflow were already on origin/main
  (b104f8f, the merge base here); this change set aligns the suite lists and
  guards them against future drift.
- The change-set key derivation (`scripts/pre-push-pipeline.sh`) resolves to
  `prepush-ece03d6cca7db790680412ae01abc161ba548b56`, matching the task body's
  key. No change-set commit carries a `Pipeline-Key:` trailer, so derivation
  stops at HEAD; a trailer added to the parent's commit will not change this.

Residual risk: low — test/CI plumbing and docs only, no production paths.

## 2. Docs

- `README.md`: current — six regression suites, six test commands, GitHub issues
  / Zero Factory triage section, ports 8888/9999/9997, all config options
  including `consolidation_max_completion_tokens` (default 8192). No edit needed.
- `hindsight/DOCS.md`: current — pre-push troubleshooting bullet now names all
  six suites (`test_source_defaults.py`, `test_ingress_rewrite.py`,
  `test_prepush_pipeline.py`, `test_version_watch.py`,
  `test_continit_providers.py`, `test_setup_gh_issues.py`). The rest of the
  file matches config.yaml and the 1.3.0 pins.
- `openwiki/` pages (generated evidence index) still describe the "five
  suites" wording; these are generated and are deliberately left untouched —
  see notes in `openwiki/workflows/index.md` and
  `openwiki/workflows/testing-and-regressions.md`.

## 3. Tests — exact commands and results

All commands run from the worktree root; each exited 0.

| Command | Exit | PASS checks |
| --- | --- | --- |
| `python3 hindsight/tests/test_source_defaults.py` | 0 | 2 (`source defaults OK`) |
| `python3 hindsight/tests/test_ingress_rewrite.py` | 0 | 18 |
| `python3 hindsight/tests/test_prepush_pipeline.py` | 0 | 82 |
| `python3 hindsight/tests/test_version_watch.py` | 0 | 20 |
| `python3 hindsight/tests/test_continit_providers.py` | 0 | 48 |
| `python3 hindsight/tests/test_setup_gh_issues.py` | 0 | 51 |

`test_source_defaults.py` prints a summary line instead of `RESULT: PASS`; all
other suites ended with `RESULT: PASS`. The new suite-drift guard in
test_prepush_pipeline.py reported `RESULT: PASS` (82 PASS checks, including the
five-source parity check, the README/DOCS six-suite check and the self-checks
that reject a missing suite and a mistyped path). No failures.

## 4. Residual risk

1. **Concurrent edits in a shared `dir` worktree.** Sibling assessment workers
   modified `hindsight/DOCS.md` and `hindsight/tests/test_prepush_pipeline.py`
   while earlier assessments ran. Their edits were preserved (not
   overwritten); serialize workers or use separate worktrees before committing.
   For this change set the docs/test edits are already committed upstream, so
   the risk is only about any further concurrent worker activity.
2. **openwiki/ is generated.** The "five suites" wording there is stale
   relative to the six-regression-suite pipeline but is not hand-edited per
   the repository maintenance process; regeneration is expected after the
   source/docs stabilise.
3. No runtime/add-on behaviour risk identified in the net diff — pure
   pipeline/doc/test alignment.

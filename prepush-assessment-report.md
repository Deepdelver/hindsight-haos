# Pre-push assessment — prepush-bfc9c66d7247f1093072f4592d8897acfe1bcd80

Worktree: /config/.zerofactory/workspaces/deepdelver-hindsight-haos/worktrees/zf-dhh-96833dcd/deepdelver-hindsight-haos
Key (derived by scripts/pre-push-pipeline.sh and stated in the task body): prepush-bfc9c66d7247f1093072f4592d8897acfe1bcd80
HEAD assessed: bfc9c66d7247f1093072f4592d8897acfe1bcd80
Base: origin/main 63e7cb381f9ec4672c385f78e08d2c71217c71b3 (also the merge base)

## 1. Assessment

Eight commits on `origin/main..HEAD` (newest first): bfc9c66d, 8df7dd4 (merge of origin/main), a4547ed, ece03d6, 8c5f9e1, 9a0965f (merge of origin/main), 1095992 (merge-conflict fix), f9c3bd1. All but the merges/conflict fix re-apply the same drift-guard change; the net diff is what matters.

Net diff `origin/main...HEAD`: 2 files changed, 178 insertions, 0 deletions.

- `hindsight/tests/test_prepush_pipeline.py` (+122) — adds a suite-list drift guard over the five places that spell out the six regression suites (precommit `REGRESSION_SUITES`, pre-push done branch, pre-push assessment task body, GitHub workflow, version-watch task body), plus self-checks proving the guard rejects a missing suite and a mistyped path. It also asserts README.md and hindsight/DOCS.md name all six suites.
- `prepush-assessment-report.md` — this report; refreshed to the current key/HEAD and re-measured results.

Behaviour changes: none in the add-on runtime. Ports (8888 API/MCP, 9999 direct UI, 9997 internal HA ingress), configuration options and defaults, config.yaml version 1.2.28, and upstream pins 1.3.0/1.3.0 are unchanged; `consolidation_max_completion_tokens` still defaults to 8192 and is emitted only with a consolidation LLM. The sixth suite (`test_setup_gh_issues.py`), its generator, issue templates and the GitHub workflow already exist on origin/main; this change set aligns the five suite lists and guards them against future drift.

No commit in the change set carries a `Pipeline-Key:` trailer, so the gate derives the key from HEAD. Adding the trailer to the parent's packaging commit keeps this key stable and allows the push.

## 2. Docs

- `README.md`: current — six suites and six test commands, ports 8888/9999/9997, all config options including `consolidation_max_completion_tokens` (default 8192). No edit needed.
- `hindsight/DOCS.md`: current — pre-push troubleshooting names all six suites; ports, configuration and 1.3.0 pins match config.yaml. No edit needed.
- `openwiki/` is a generated evidence index and still uses older "five suites" wording; left untouched per the repository maintenance process.

## 3. Tests — exact commands and results

Run from the worktree root; each exited 0.

| Command | Exit | Result | PASS checks |
| --- | --- | --- | --- |
| `python3 hindsight/tests/test_source_defaults.py` | 0 | `source defaults OK` | 2 |
| `python3 hindsight/tests/test_ingress_rewrite.py` | 0 | `RESULT: PASS` | 18 |
| `python3 hindsight/tests/test_prepush_pipeline.py` | 0 | `RESULT: PASS` | 82 |
| `python3 hindsight/tests/test_version_watch.py` | 0 | `RESULT: PASS` | 20 |
| `python3 hindsight/tests/test_continit_providers.py` | 0 | `RESULT: PASS` | 48 |
| `python3 hindsight/tests/test_setup_gh_issues.py` | 0 | `RESULT: PASS` | 51 |

`bash .zerofactory/precommit.sh all` also exits 0 (format, build and all six suites). Running `bash scripts/pre-push-pipeline.sh` directly here exited 1 with `kanban: delegate_task child contexts cannot mutate Kanban tasks via the CLI` — a delegated-context restriction, not a pipeline defect; the gate's own behaviour is covered by the fake git/hermes end-to-end checks in `test_prepush_pipeline.py`, which pass.

## 4. Residual risk

1. The change set consists of test/CI plumbing and documentation only; no production path is touched, so runtime regression risk is low.
2. The shared `dir` worktree has been edited by several sibling assessment workers. Keep further edits serialized and leave them uncommitted for the parent to commit with the `Pipeline-Key` trailer.
3. `openwiki/` wording is generated and stale relative to six suites; regenerate it through the documented maintenance flow rather than editing by hand.

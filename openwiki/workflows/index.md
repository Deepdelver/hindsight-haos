# Files

- [Version pinning, drift detection and release gates](release-and-version-watch.md) - How matching Hindsight API and Control Plane versions are pinned and recorded, how the daily drift watch raises an idempotent Kanban task, and how the pre-push and GitHub gates enforce assessment before release.
- [Regression suites and precommit gate](testing-and-regressions.md) - Why each standalone Python regression suite exists, what invariant it protects, how precommit.sh runs format/build/test phases and how the same five suites run in the pre-push gate and CI.

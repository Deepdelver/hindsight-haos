#!/usr/bin/env python3
"""Regression tests for the vendored Zero Factory GitHub issue-setup generator.

The documented command must work from a fresh checkout:

    python3 scripts/setup_gh_issues.py --path . --align

These tests cover template contents, align/non-align semantics, repo-aware
config generation, git remote detection, label provisioning and the CLI entry
point. No third-party runtime dependency is required; when PyYAML happens to
be installed it is used for an extra parse check, otherwise that check is
skipped.

Run: python3 hindsight/tests/test_setup_gh_issues.py
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup_gh_issues.py"
TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
REPO_SLUG = "Deepdelver/hindsight-haos"

BUG_LABELS = 'labels: ["bug", "zerofactory"]'
FEATURE_LABELS = 'labels: ["feature", "zerofactory"]'


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
        return True
    print(f"FAIL  {name}  {detail}")
    return False


def load_module():
    spec = importlib.util.spec_from_file_location("setup_gh_issues", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def run_detection(mod, output, returncode=0):
    with patch.object(mod.subprocess, "run", return_value=completed(returncode, output)):
        return mod.detect_repo_from_git(ROOT)


def main():
    ok = check("generator is vendored in the repository", SCRIPT.is_file())
    if not SCRIPT.is_file():
        print("\nRESULT: FAIL")
        return 1

    mod = load_module()

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"

        # --- 1. Template contents ---------------------------------------------
        written = mod.setup_github_issue_templates(repo, repo=REPO_SLUG, align=True)
        bug = repo / ".github/ISSUE_TEMPLATE/bug_report.yml"
        feature = repo / ".github/ISSUE_TEMPLATE/feature_request.yml"
        config = repo / ".github/ISSUE_TEMPLATE/config.yml"

        bug_text = bug.read_text(encoding="utf-8")
        feature_text = feature.read_text(encoding="utf-8")
        config_text = config.read_text(encoding="utf-8")

        ok &= check("bug report carries bug + zerofactory labels", BUG_LABELS in bug_text)
        ok &= check(
            "feature request carries feature + zerofactory labels", FEATURE_LABELS in feature_text
        )
        for section in ("id: problem", "id: reproduction", "id: expected", "id: ai_investigate"):
            ok &= check(f"bug report has {section}", section in bug_text)
        for section in ("id: summary", "id: solution", "id: constraints", "id: ai_investigate"):
            ok &= check(f"feature request has {section}", section in feature_text)
        ok &= check("required sections are validated", "required: true" in bug_text)
        ok &= check(
            "AI investigation is an opt-in checkbox",
            "type: checkboxes" in bug_text and "required: false" in bug_text,
        )

        # --- 2. Repo-aware config ---------------------------------------------
        ok &= check("config disables blank issues", "blank_issues_enabled: false" in config_text)
        ok &= check(
            "config points at this repository's Discussions",
            "https://github.com/Deepdelver/hindsight-haos/discussions" in config_text,
        )
        ok &= check("config offers a Discussions contact link", "GitHub Discussions" in config_text)
        ok &= check(
            "config falls back for an unknown repo",
            "https://github.com/hotcode-dev/zerofactory/discussions"
            in mod.build_config_template(repo=None),
        )
        ok &= check(
            "config falls back for an invalid slug",
            "https://github.com/hotcode-dev/zerofactory/discussions"
            in mod.build_config_template(repo="not-a-slug"),
        )

        # --- 3. Optional YAML parse -------------------------------------------
        try:
            import yaml
        except ImportError:
            print("SKIP  YAML parse check (PyYAML not installed)")
        else:
            for name, path in (
                ("bug_report.yml", bug),
                ("feature_request.yml", feature),
                ("config.yml", config),
            ):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                ok &= check(f"{name} parses to a mapping", isinstance(data, dict))

        # --- 4. Align mode -----------------------------------------------------
        ok &= check(
            "align creates all three templates when missing",
            {p.name for p in written} == {"bug_report.yml", "feature_request.yml", "config.yml"},
            str([p.name for p in written]),
        )

        custom_dir = repo / "custom" / ".github" / "ISSUE_TEMPLATE"
        custom_dir.mkdir(parents=True)
        custom_bug = custom_dir / "bug_report.yml"
        custom_text = 'name: "Custom"\nlabels: ["bug", "zerofactory"]\nbody: custom\n'
        custom_bug.write_text(custom_text, encoding="utf-8")
        custom_config = custom_dir / "config.yml"
        custom_config.write_text("blank_issues_enabled: true\n", encoding="utf-8")
        mod.setup_github_issue_templates(repo / "custom", repo=REPO_SLUG, align=True)
        ok &= check(
            "align preserves a customized template that carries the label",
            custom_bug.read_text(encoding="utf-8") == custom_text,
        )
        ok &= check(
            "align always regenerates config.yml",
            "blank_issues_enabled: false" in custom_config.read_text(encoding="utf-8"),
        )

        stale_dir = repo / "stale" / ".github" / "ISSUE_TEMPLATE"
        stale_dir.mkdir(parents=True)
        stale_bug = stale_dir / "bug_report.yml"
        stale_bug.write_text('name: "Old"\nlabels: ["bug"]\n', encoding="utf-8")
        mod.setup_github_issue_templates(repo / "stale", repo=REPO_SLUG, align=True)
        ok &= check(
            "align rewrites a template missing the zerofactory label",
            "zerofactory" in stale_bug.read_text(encoding="utf-8"),
        )

        ok &= check(
            "label detection tolerates whitespace",
            mod._template_has_expected_labels(
                'name: X\nlabels: [ "bug" ,  "zerofactory" ]\n', ("bug", "zerofactory")
            ),
        )
        ok &= check(
            "label detection rejects a partial label set",
            not mod._template_has_expected_labels(
                'name: X\nlabels: ["bug"]\n', ("bug", "zerofactory")
            ),
        )

        overwrite_dir = repo / "overwrite" / ".github" / "ISSUE_TEMPLATE"
        overwrite_dir.mkdir(parents=True)
        overwrite_bug = overwrite_dir / "bug_report.yml"
        overwrite_bug.write_text(custom_text, encoding="utf-8")
        mod.setup_github_issue_templates(repo / "overwrite", repo=REPO_SLUG, align=False)
        ok &= check(
            "non-align mode overwrites customized templates",
            "Problem Description" in overwrite_bug.read_text(encoding="utf-8"),
        )

        # --- 5. Git remote detection ------------------------------------------
        for remote in (
            "https://github.com/Deepdelver/hindsight-haos.git\n",
            "git@github.com:Deepdelver/hindsight-haos.git\n",
            "https://github.com/Deepdelver/hindsight-haos\n",
        ):
            ok &= check(
                f"detects repo from {remote.strip()}",
                run_detection(mod, remote) == REPO_SLUG,
                str(run_detection(mod, remote)),
            )
        ok &= check("detection returns None when git fails", run_detection(mod, "", 128) is None)
        ok &= check(
            "detection ignores non-GitHub remotes",
            run_detection(mod, "https://gitlab.com/foo/bar.git\n") is None,
        )
        with patch.object(mod.subprocess, "run", side_effect=OSError("no git")):
            ok &= check(
                "detection survives a subprocess error", mod.detect_repo_from_git(ROOT) is None
            )
        with patch.dict(
            os.environ,
            {"GIT_DIR": str(ROOT / ".git"), "GIT_WORK_TREE": str(ROOT)},
        ):
            hook_env_result = mod.detect_repo_from_git(repo)
        ok &= check(
            "detection ignores git env inherited from a hook",
            hook_env_result is None,
            str(hook_env_result),
        )

        # --- 6. Label provisioning --------------------------------------------
        expected_labels = {
            "zerofactory": "7c3aed",
            "ai-investigate": "8b5cf6",
            "bug": "d73a4a",
            "feature": "a2eeef",
            "p0": "b60205",
            "p1": "d93f0b",
            "p2": "fbca04",
            "p3": "0e8a16",
        }
        ok &= check(
            "standard labels have the expected names and colors",
            {lbl["name"]: lbl["color"] for lbl in mod.STANDARD_LABELS} == expected_labels,
        )
        ok &= check(
            "every label has a description",
            all(lbl.get("description") for lbl in mod.STANDARD_LABELS),
        )

        with patch.object(mod.shutil, "which", return_value=None):
            missing_gh = mod.provision_github_labels(REPO_SLUG)
        ok &= check(
            "label provisioning degrades gracefully without gh",
            not missing_gh["ok"] and not missing_gh["created"] and "gh" in missing_gh["error"],
            str(missing_gh),
        )

        with (
            patch.object(mod.shutil, "which", return_value="/usr/bin/gh"),
            patch.object(mod.subprocess, "run", return_value=completed()) as run,
        ):
            created = mod.provision_github_labels(REPO_SLUG)
        ok &= check(
            "label provisioning creates all eight labels via gh",
            created["ok"] and len(created["created"]) == 8 and run.call_count == 8,
            str(created),
        )
        first_cmd = run.call_args_list[0].args[0]
        ok &= check(
            "gh commands target the repo and force-update labels",
            first_cmd[:3] == ["gh", "label", "create"]
            and REPO_SLUG in first_cmd
            and "--force" in first_cmd,
            str(first_cmd),
        )

        with (
            patch.object(mod.shutil, "which", return_value="/usr/bin/gh"),
            patch.object(mod.subprocess, "run", return_value=completed(1, stderr="denied")),
        ):
            failed = mod.provision_github_labels(REPO_SLUG)
        ok &= check(
            "label provisioning records gh failures",
            not failed["ok"] and not failed["created"] and "denied" in failed["failed"][0],
            str(failed),
        )

        with (
            patch.object(mod.shutil, "which", return_value="/usr/bin/gh"),
            patch.object(mod.subprocess, "run", side_effect=OSError("boom")),
        ):
            raised = mod.provision_github_labels(REPO_SLUG)
        ok &= check(
            "label provisioning survives a subprocess error",
            not raised["ok"] and "boom" in raised["failed"][0],
            str(raised),
        )

        # --- 7. Unified setup entry point -------------------------------------
        with patch.object(mod, "provision_github_labels") as provision:
            skipped = mod.setup_github_issues(repo, repo=REPO_SLUG, create_labels=False, align=True)
        provision.assert_not_called()
        ok &= check(
            "setup can skip label provisioning",
            skipped["ok"] and skipped["label_results"] is None,
            str(skipped),
        )

        no_repo = mod.setup_github_issues(repo, repo=None, create_labels=True, align=True)
        ok &= check(
            "setup reports a label failure when no repo can be determined",
            no_repo["ok"]
            and not no_repo["label_results"]["ok"]
            and "Could not determine" in no_repo["label_results"]["error"],
            str(no_repo["label_results"]),
        )

        # --- 8. CLI end to end -------------------------------------------------
        cli_repo = repo / "cli"
        cli = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--path",
                str(cli_repo),
                "--repo",
                REPO_SLUG,
                "--no-labels",
                "--align",
            ],
            capture_output=True,
            text=True,
        )
        cli_dir = cli_repo / ".github/ISSUE_TEMPLATE"
        ok &= check(
            "CLI generates aligned templates without label writes",
            cli.returncode == 0
            and (cli_dir / "bug_report.yml").is_file()
            and BUG_LABELS in (cli_dir / "bug_report.yml").read_text(encoding="utf-8")
            and (cli_dir / "feature_request.yml").is_file()
            and (cli_dir / "config.yml").is_file(),
            f"rc={cli.returncode} stderr={cli.stderr.strip()}",
        )

    # --- 9. The committed artifacts themselves --------------------------------
    ok &= check("committed bug_report.yml exists", (TEMPLATE_DIR / "bug_report.yml").is_file())
    ok &= check(
        "committed bug_report.yml carries the expected labels",
        BUG_LABELS in (TEMPLATE_DIR / "bug_report.yml").read_text(encoding="utf-8"),
    )
    ok &= check(
        "committed feature_request.yml exists", (TEMPLATE_DIR / "feature_request.yml").is_file()
    )
    ok &= check(
        "committed feature_request.yml carries the expected labels",
        FEATURE_LABELS in (TEMPLATE_DIR / "feature_request.yml").read_text(encoding="utf-8"),
    )
    ok &= check("committed config.yml exists", (TEMPLATE_DIR / "config.yml").is_file())
    ok &= check(
        "committed config.yml disables blank issues",
        "blank_issues_enabled: false" in (TEMPLATE_DIR / "config.yml").read_text(encoding="utf-8"),
    )

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

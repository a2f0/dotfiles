"""Claude Code status line folder and weekly cap regressions."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "files" / "claude" / "statusline.py"
SPEC = importlib.util.spec_from_file_location("claude_statusline", SCRIPT)
statusline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(statusline)

HOME = "/u/me"


def segment(icon, cwd, text):
    return f"{icon} \x1b]8;;file://{cwd}\x07{text}\x1b]8;;\x07"


class FolderTests(unittest.TestCase):
    def folder(self, cwd, scratch=()):
        return statusline.folder(cwd, HOME, list(scratch))

    def test_home_is_abbreviated_and_long_paths_keep_their_end(self):
        self.assertEqual(
            self.folder("/u/me/dotfiles"),
            segment("📁", "/u/me/dotfiles", "~/dotfiles"),
        )
        long = "/u/me/code/an-unusually-long-project/with/nested/src"
        self.assertEqual(
            self.folder(long),
            segment("📁", long, "…-unusually-long-project/with/nested/src"),
        )

    def test_project_roots_are_dropped_below_them(self):
        for cwd, text in (
            ("/u/me/Projects/app/src", "app/src"),
            ("/u/me/repos/tool", "tool"),
            ("/work/service", "service"),
            ("/u/me/Projects", "~/Projects"),
        ):
            with self.subTest(cwd=cwd):
                self.assertEqual(self.folder(cwd), segment("📁", cwd, text))

    def test_scratch_directories_are_relative_to_their_root(self):
        self.assertEqual(
            self.folder("/scratch/build/out", ["/scratch"]),
            segment("🗑", "/scratch/build/out", "build/out"),
        )
        self.assertEqual(
            self.folder("/scratch", ["/scratch"]),
            segment("🗑", "/scratch", "/scratch"),
        )

    def test_control_characters_cannot_reach_the_terminal(self):
        output = self.folder("/u/me/x\x1b]0;owned\x07")
        self.assertEqual(
            output,
            segment("📁", "/u/me/x%1B%5D0%3Bowned%07", "~/x?]0;owned?"),
        )


class WorktreeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.env = os.environ | {
            "CLAUDE_CONFIG_DIR": str(self.root),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(name, None)
        self.project = self.root / "project"
        self.git("init", "--quiet", "-b", "main", str(self.project))
        self.git("-C", str(self.project), "commit", "--quiet", "--allow-empty", "-m", "init")

    def git(self, *args):
        subprocess.run(
            ["git", *args], env=self.env, check=True, capture_output=True, timeout=30,
        )

    def worktree(self, repository, directory, branch):
        path = self.root / directory
        self.git("-C", str(repository), "worktree", "add", "--quiet", "-b", branch, str(path))
        return path

    def render(self, cwd, **data):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps({"workspace": {"current_dir": str(cwd)}, **data}),
            env=self.env, check=True, capture_output=True, text=True, timeout=30,
        )
        return result.stdout

    def test_weekly_caps_combine_live_and_account_scoped_cache(self):
        now = datetime.now(timezone.utc)
        window = {"resets_at": (now + timedelta(days=1)).isoformat()}
        scoped = {"kind": "weekly_scoped", "scope": {"model": {"display_name": "Fable"}}}
        rows = [
            dict(window, kind="weekly_all", percent=30),
            dict(window, **scoped, percent=0),
            dict(window, kind="session", percent=90),
            dict(window, kind="weekly_scoped", percent=80, scope={"model": {"display_name": "Opus"}}),
            dict(scoped, percent=50, resets_at=(now - timedelta(minutes=1)).isoformat()),
            dict(window, kind="weekly_scoped", percent=75, scope={"surface": {"display_name": "Code"}}),
        ]
        config = {
            "oauthAccount": {"accountUuid": "test-account"},
            "cachedUsageUtilization": {
                "accountUuid": "test-account",
                "fetchedAtMs": int((now - timedelta(hours=2)).timestamp() * 1000),
                "utilization": {"limits": rows},
            },
        }
        state = self.root / ".claude.json"
        state.write_text(json.dumps(config))
        self.assertIn("7d All 30% used (2h ago) · Fable 0% used (2h ago)\n", self.render(self.project))
        fallback = self.render(self.project)
        for unusable in ("invalid", {"seven_day": [1]}, {"seven_day": {"used_percentage": 80, "resets_at": 1}}):
            with self.subTest(rate_limits=unusable):
                self.assertEqual(self.render(self.project, rate_limits=unusable), fallback)
        limits = {"seven_day": {"used_percentage": 41.2, "resets_at": now.timestamp() + 3600}}
        self.assertIn("7d All 41% used · Fable 0% used (2h ago)\n", self.render(self.project, rate_limits=limits))
        config["oauthAccount"]["accountUuid"] = "switched-account"
        state.write_text(json.dumps(config))
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(" | 7d All 41% used\n"))
        state.write_text("{")
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(" | 7d All 41% used\n"))

    def test_worktrees_show_the_project_and_any_unbranched_directory(self):
        named = self.worktree(self.project, "feature", "feature")
        (named / "src").mkdir()
        other = self.worktree(self.project, "checkout-2", "topic")
        self.assertEqual(self.render(named / "src"), segment("🌳", named / "src", "project") + "\n")
        self.assertEqual(self.render(other), segment("🌳", other, "project/checkout-2") + "\n")
        # The primary checkout is a folder, here inside the temporary scratch root.
        self.assertTrue(self.render(self.project).startswith("🗑 "))

    def test_bare_repository_worktrees_drop_the_git_suffix(self):
        bare = self.root / "shared.git"
        self.git("clone", "--quiet", "--bare", str(self.project), str(bare))
        checkout = self.worktree(bare, "bare-checkout", "topic")
        self.assertEqual(self.render(checkout), segment("🌳", checkout, "shared/bare-checkout") + "\n")


if __name__ == "__main__":
    unittest.main()

"""Claude Code status line folder, model, identity, and weekly cap regressions."""

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


class ModelTests(unittest.TestCase):
    def test_the_model_shows_its_effort_level(self):
        model = {"id": "claude-opus-5-5", "display_name": "Opus 5.5"}
        self.assertEqual(
            statusline.model_label({"model": model, "effort": {"level": "xhigh"}}),
            "🤖 Opus 5.5 · xhigh",
        )
        # Claude Code omits `effort` for models without the effort parameter.
        self.assertEqual(statusline.model_label({"model": model}), "🤖 Opus 5.5")

    def test_the_identifier_stands_in_for_a_missing_display_name(self):
        for model in ({"id": "claude-opus-5-5"}, {"id": "claude-opus-5-5", "display_name": ""}):
            with self.subTest(model=model):
                self.assertEqual(
                    statusline.model_label({"model": model, "effort": {"level": "high"}}),
                    "🤖 claude-opus-5-5 · high",
                )

    def test_unusable_fields_are_skipped(self):
        for data in (
            {}, {"model": None}, {"model": "Opus"}, {"model": {"display_name": 5}},
            {"effort": {"level": ""}}, {"effort": {"level": "xhigh"}},
            {"model": {"id": ""}, "effort": {"level": "xhigh"}},
        ):
            with self.subTest(data=data):
                self.assertIsNone(statusline.model_label(data))
        self.assertEqual(statusline.model_label({"model": {"id": "m"}, "effort": "high"}), "🤖 m")
        self.assertEqual(statusline.model_label({"model": {"id": "m"}, "effort": {"level": ["high"]}}), "🤖 m")

    def test_control_characters_cannot_reach_the_terminal(self):
        data = {"model": {"display_name": "Opus\x1b]0;owned\x07"}, "effort": {"level": "x\x1b[2J"}}
        self.assertEqual(statusline.model_label(data), "🤖 Opus?]0;owned? · x?[2J")

    def test_long_parts_keep_their_end(self):
        data = {"model": {"display_name": "An Extraordinarily Long Model Name (1M context)"}, "effort": {"level": "xhigh"}}
        self.assertEqual(statusline.model_label(data), "🤖 …ordinarily Long Model Name (1M context) · xhigh")


class IdentityTests(unittest.TestCase):
    def test_only_an_override_is_shown_relative_to_home(self):
        for value in (None, ""):
            with self.subTest(value=value):
                self.assertIsNone(statusline.identity_label(value, HOME))
                self.assertIsNone(statusline.identity_label(value, HOME, ""))
        self.assertEqual(statusline.identity_label("/u/me/.claude2", HOME), "⚙ ~/.claude2")
        self.assertEqual(statusline.identity_label("/srv/claude", HOME), "⚙ /srv/claude")
        long = "/u/me/accounts/an-unusually-long-name/.claude"
        self.assertEqual(statusline.identity_label(long, HOME), "⚙ …accounts/an-unusually-long-name/.claude")

    def test_the_email_shares_the_segment(self):
        self.assertEqual(
            statusline.identity_label("/u/me/.claude2", HOME, "someone@example.com"),
            "⚙ ~/.claude2 · someone@example.com",
        )
        self.assertEqual(statusline.identity_label(None, HOME, "someone@example.com"), "⚙ someone@example.com")
        long = "a.very.long.mailbox.name@an-unusually-long.example.com"
        self.assertEqual(statusline.identity_label(None, HOME, long), "⚙ …lbox.name@an-unusually-long.example.com")

    def test_control_characters_cannot_reach_the_terminal(self):
        self.assertEqual(statusline.identity_label("/u/me/x\x1b]0;owned\x07", HOME), "⚙ ~/x?]0;owned?")
        self.assertEqual(statusline.identity_label(None, HOME, "a\x1b]0;owned\x07@example.com"), "⚙ a?]0;owned?@example.com")

    def test_the_email_requires_the_session_account(self):
        state = {"oauthAccount": {"accountUuid": "test-account", "emailAddress": "someone@example.com"}}
        self.assertEqual(statusline.signed_in_email(state, "test-account"), "someone@example.com")
        for account in (None, "", "other-account"):
            with self.subTest(account=account):
                self.assertIsNone(statusline.signed_in_email(state, account))
        for unusable in (
            None, [], "text", {}, {"oauthAccount": None},
            {"oauthAccount": {"accountUuid": "test-account"}},
            {"oauthAccount": {"emailAddress": "someone@example.com"}},
            {"oauthAccount": {"accountUuid": "test-account", "emailAddress": ""}},
            {"oauthAccount": {"accountUuid": "test-account", "emailAddress": ["someone@example.com"]}},
        ):
            with self.subTest(state=unusable):
                self.assertIsNone(statusline.signed_in_email(unusable, "test-account"))


class WorktreeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.env = os.environ | {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(name, None)
        self.env.pop("CLAUDE_CODE_ACCOUNT_UUID", None)
        self.env.pop("CLAUDE_CONFIG_DIR", None)
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
            input=json.dumps({
                "workspace": {"current_dir": str(cwd)},
                "session_id": "session",
                "transcript_path": str(self.root / "session.jsonl"),
                **data,
            }),
            env=self.env, check=True, capture_output=True, text=True, timeout=30,
        )
        return result.stdout

    def test_weekly_caps_combine_live_and_account_scoped_cache(self):
        now = datetime.now(timezone.utc)
        window = {"resets_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.1234Z")}
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
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root)
        plain = self.render(self.project)
        label = statusline.identity_label(str(self.root), os.path.expanduser("~"))
        self.assertTrue(label and plain.endswith(f" | {label}\n"))
        state.write_text(json.dumps(config))
        self.assertEqual(self.render(self.project), plain)
        for unusable in ("invalid", {"seven_day": [1]}, {"spend_limit": {"used_percentage": 10}}):
            with self.subTest(rate_limits=unusable):
                self.assertEqual(self.render(self.project, rate_limits=unusable), plain)
        transcript = self.root / "session.jsonl"
        owner = {"accountUuid": "test-account", "sessionId": "session", "type": "session-owner"}
        transcript.write_text(json.dumps(owner) + '\n{"type":"session-owner",')
        session = {"five_hour": {"used_percentage": 15}}
        fallback = self.render(self.project, rate_limits=session)
        self.assertIn("7d All 30% used (2h ago) · Fable 0% used (2h ago)\n", fallback)
        expired = {"seven_day": {"used_percentage": 80, "resets_at": 1}}
        self.assertEqual(self.render(self.project, rate_limits=session | expired), fallback)
        limits = {"seven_day": {"used_percentage": 41.2, "resets_at": now.timestamp() + 3600}}
        both = "7d All 41% used | Account 7d Fable 0% used (2h ago)\n"
        self.assertEqual(self.render(self.project, rate_limits=limits), plain[:-1] + " | " + both)
        rows[0]["resets_at"] = (now - timedelta(seconds=1)).isoformat()
        state.write_text(json.dumps(config))
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(both))
        transcript.unlink()
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(" | 7d All 41% used\n"))
        previous = dict(owner, accountUuid="previous-account")
        transcript.write_text(json.dumps(previous, separators=(",", ":")) + "\n")
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(" | 7d All 41% used\n"))
        with transcript.open("a") as source:
            source.write(json.dumps(owner, separators=(",", ":")) + "\n")
        self.env["CLAUDE_CODE_ACCOUNT_UUID"] = "previous-account"
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(" | 7d All 41% used\n"))
        self.env["CLAUDE_CODE_ACCOUNT_UUID"] = "test-account"
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(both))
        self.env.pop("CLAUDE_CODE_ACCOUNT_UUID")
        config["cachedUsageUtilization"]["utilization"]["limits"] = [dict(window, kind="weekly_all", percent=30)]
        state.write_text(json.dumps(config))
        self.assertTrue(self.render(self.project, rate_limits=session).endswith(" | Account 7d All 30% used (2h ago)\n"))
        config["oauthAccount"]["accountUuid"] = "switched-account"
        state.write_text(json.dumps(config))
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(" | 7d All 41% used\n"))
        state.write_text("{")
        self.assertTrue(self.render(self.project, rate_limits=limits).endswith(" | 7d All 41% used\n"))

    def test_identity_shows_the_session_accounts_email(self):
        state = {"oauthAccount": {"accountUuid": "test-account", "emailAddress": "someone@example.com"}}
        (self.root / ".claude.json").write_text(json.dumps(state))
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root)
        directory = statusline.identity_label(str(self.root), os.path.expanduser("~"))
        # Without a known session account, only the directory override shows.
        self.assertTrue(self.render(self.project).endswith(f" | {directory}\n"))
        owner = {"accountUuid": "test-account", "sessionId": "session", "type": "session-owner"}
        (self.root / "session.jsonl").write_text(json.dumps(owner) + "\n")
        self.assertTrue(self.render(self.project).endswith(f" | {directory} · someone@example.com\n"))
        self.env["CLAUDE_CODE_ACCOUNT_UUID"] = "other-account"
        self.assertTrue(self.render(self.project).endswith(f" | {directory}\n"))
        self.env["CLAUDE_CODE_ACCOUNT_UUID"] = "test-account"
        self.assertTrue(self.render(self.project).endswith(f" | {directory} · someone@example.com\n"))
        # The default directory adds no override, so the email stands alone.
        self.env.pop("CLAUDE_CONFIG_DIR")
        self.env["HOME"] = str(self.root)
        self.assertTrue(self.render(self.project).endswith(" | ⚙ someone@example.com\n"))

    def test_the_model_follows_the_folder(self):
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root)
        plain = self.render(self.project)
        folder, _, identity = plain.partition(" | ")
        data = {"model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"}, "effort": {"level": "xhigh"}}
        self.assertEqual(self.render(self.project, **data), f"{folder} | 🤖 Opus 5.5 · xhigh | {identity}")

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

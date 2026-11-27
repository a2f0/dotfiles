"""Antigravity CLI status line host, folder, branch, model, identity, context, and quota regressions."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "files" / "antigravity-cli" / "statusline.py"
SPEC = importlib.util.spec_from_file_location("antigravity_statusline", SCRIPT)
statusline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(statusline)

HOME = "/u/me"


def segment(icon, cwd, text):
    return f"{icon} \x1b]8;;file://{cwd}\x07{text}\x1b]8;;\x07"


class HostTests(unittest.TestCase):
    def test_the_domain_is_dropped(self):
        for hostname, label in (
            ("laptop.local", "💻 laptop"),
            ("build-01.example.com", "💻 build-01"),
            ("workstation", "💻 workstation"),
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(statusline.host_label(hostname), label)

    def test_an_empty_name_hides_the_segment(self):
        for hostname in ("", ".local"):
            with self.subTest(hostname=hostname):
                self.assertIsNone(statusline.host_label(hostname))

    def test_long_names_keep_their_end(self):
        long = "an-unusually-long-hostname-for-a-build-machine.example.com"
        self.assertEqual(statusline.host_label(long), "💻 …ually-long-hostname-for-a-build-machine")

    def test_control_characters_cannot_reach_the_terminal(self):
        self.assertEqual(statusline.host_label("x\x1b]0;owned\x07"), "💻 x?]0;owned?")


class BranchTests(unittest.TestCase):
    def test_the_branch_is_named(self):
        self.assertEqual(statusline.branch_label("feat/topic"), "🌿 feat/topic")
        self.assertEqual(statusline.branch_label("(3bd8603)"), "🌿 (3bd8603)")

    def test_no_branch_hides_the_segment(self):
        for branch in (None, ""):
            with self.subTest(branch=branch):
                self.assertIsNone(statusline.branch_label(branch))

    def test_long_names_keep_their_end(self):
        long = "feat/an-unusually-long-topic-name-for-a-branch"
        self.assertEqual(statusline.branch_label(long), "🌿 …-unusually-long-topic-name-for-a-branch")

    def test_control_characters_cannot_reach_the_terminal(self):
        self.assertEqual(statusline.branch_label("x\x1b]0;owned\x07"), "🌿 x?]0;owned?")


class GitDeadlineTests(unittest.TestCase):
    def test_queries_share_one_deadline(self):
        timeouts = []

        def run(args, **options):
            timeouts.append(options["timeout"])
            clock[0] += 1
            if args[3] == "symbolic-ref":
                return subprocess.CompletedProcess(args, 1, "", "")
            return subprocess.CompletedProcess(args, 0, "/r/.git\n/r/.git\n/r\n", "")

        clock = [100.0]
        with mock.patch.object(statusline.time, "monotonic", lambda: clock[0]), \
                mock.patch.object(statusline.subprocess, "run", run):
            self.assertEqual(statusline.git_labels("/r"), (None, None))
        self.assertEqual(timeouts, [2, 1])

    def test_a_passed_deadline_starts_no_query(self):
        with mock.patch.object(statusline.subprocess, "run") as run:
            self.assertIsNone(statusline.git("/r", statusline.time.monotonic() - 1, "status"))
        run.assert_not_called()


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
    def test_the_model_shows_effort_unless_already_in_display_name(self):
        self.assertEqual(
            statusline.model_label({
                "model": {
                    "id": "gemini-4-neon-high",
                    "display_name": "Gemini 4 Neon (High)",
                    "effort": "high",
                },
            }),
            "🤖 Gemini 4 Neon (High)",
        )
        self.assertEqual(
            statusline.model_label({
                "model": {
                    "id": "gemini-4-pro",
                    "display_name": "Gemini 4 Pro",
                    "effort": "xhigh",
                },
            }),
            "🤖 Gemini 4 Pro · xhigh",
        )
        self.assertEqual(
            statusline.model_label({
                "model": {"id": "gemini-4-pro", "display_name": "Gemini 4 Pro"},
            }),
            "🤖 Gemini 4 Pro",
        )

    def test_the_identifier_stands_in_for_a_missing_display_name(self):
        for model in (
            {"id": "gemini-4-pro", "effort": "high"},
            {"id": "gemini-4-pro", "display_name": "", "effort": "high"},
        ):
            with self.subTest(model=model):
                self.assertEqual(statusline.model_label({"model": model}), "🤖 gemini-4-pro · high")

    def test_unusable_fields_are_skipped(self):
        for data in (
            {}, {"model": None}, {"model": "Gemini"}, {"model": {"display_name": 5}},
            {"model": {"id": "", "effort": "high"}},
        ):
            with self.subTest(data=data):
                self.assertIsNone(statusline.model_label(data))
        self.assertEqual(statusline.model_label({"model": {"id": "m", "effort": ["high"]}}), "🤖 m")

    def test_control_characters_cannot_reach_the_terminal(self):
        data = {"model": {"display_name": "Gemini\x1b]0;owned\x07", "effort": "x\x1b[2J"}}
        self.assertEqual(statusline.model_label(data), "🤖 Gemini?]0;owned? · x?[2J")

    def test_long_parts_keep_their_end(self):
        data = {"model": {"display_name": "An Extraordinarily Long Model Name (1M context)", "effort": "xhigh"}}
        self.assertEqual(statusline.model_label(data), "🤖 …ordinarily Long Model Name (1M context) · xhigh")


class IdentityTests(unittest.TestCase):
    def test_email_is_shown_clamped_and_sanitized(self):
        for data in ({}, {"email": None}, {"email": ""}, {"email": ["someone@example.com"]}):
            with self.subTest(data=data):
                self.assertIsNone(statusline.identity_label(data))
        self.assertEqual(statusline.identity_label({"email": "developer@example.com"}), "⚙ developer@example.com")
        long = "a.very.long.mailbox.name@an-unusually-long.example.com"
        self.assertEqual(statusline.identity_label({"email": long}), "⚙ …lbox.name@an-unusually-long.example.com")
        self.assertEqual(statusline.identity_label({"email": "a\x1b]0;owned\x07@example.com"}), "⚙ a?]0;owned?@example.com")


class ContextTests(unittest.TestCase):
    def test_context_shows_used_percentage_when_window_and_usage_are_known(self):
        self.assertEqual(
            statusline.context_label({
                "context_window": {
                    "context_window_size": 1048576,
                    "used_percentage": 14.24,
                    "current_usage": {"input_tokens": 63382},
                },
            }),
            "ctx 14%",
        )

    def test_context_is_hidden_before_first_response_or_with_unusable_fields(self):
        for window in (
            None,
            "invalid",
            {},
            {"context_window_size": 1048576, "used_percentage": 0, "current_usage": None},
            {"context_window_size": 0, "used_percentage": 14, "current_usage": {"input_tokens": 1}},
            {"context_window_size": True, "used_percentage": 14, "current_usage": {"input_tokens": 1}},
            {"context_window_size": float("nan"), "used_percentage": 14, "current_usage": {"input_tokens": 1}},
            {"context_window_size": 1048576, "used_percentage": True, "current_usage": {"input_tokens": 1}},
            {"context_window_size": 1048576, "used_percentage": -1, "current_usage": {"input_tokens": 1}},
            {"context_window_size": 1048576, "used_percentage": 101, "current_usage": {"input_tokens": 1}},
            {"context_window_size": 1048576, "used_percentage": float("nan"), "current_usage": {"input_tokens": 1}},
        ):
            with self.subTest(window=window):
                self.assertIsNone(statusline.context_label({"context_window": window}))


class QuotaTests(unittest.TestCase):
    def test_active_quota_buckets_show_percentage_used(self):
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        future = (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S.1234Z")
        past = (now - timedelta(seconds=1)).isoformat()
        data = {
            "quota": {
                "gemini-weekly": {
                    "remaining_fraction": 0.9378,
                    "reset_time": future,
                    "reset_in_seconds": 432000,
                },
                "claude-weekly": {
                    "remaining_fraction": 0.5,
                    "reset_in_seconds": 3600,
                },
                "fresh-bucket": {
                    "remaining_fraction": 1.0,
                    "reset_in_seconds": 0,
                },
                "expired-time": {
                    "remaining_fraction": 0.2,
                    "reset_time": past,
                },
                "expired-seconds": {
                    "remaining_fraction": 0.2,
                    "reset_in_seconds": 0,
                },
                "disabled-bucket": {
                    "remaining_fraction": 0.5,
                    "reset_time": future,
                    "disabled": True,
                },
                "credits-only": {
                    "remaining_amount": 100,
                    "reset_time": future,
                },
                "naive-timestamp": {
                    "remaining_fraction": 0.5,
                    "reset_time": "2026-07-06T07:50:32",
                },
                "bad-fraction": {
                    "remaining_fraction": True,
                    "reset_time": future,
                },
                "nan-seconds": {
                    "remaining_fraction": 0.5,
                    "reset_in_seconds": float("nan"),
                },
            },
        }
        self.assertEqual(
            statusline.quota_label(data, now),
            "claude-weekly 50% used · fresh-bucket 0% used · gemini-weekly 6% used",
        )

    def test_bucket_names_are_clamped_and_sanitized(self):
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        future = (now + timedelta(hours=1)).isoformat()
        data = {
            "quota": {
                "x\x1b]0;owned\x07": {"remaining_fraction": 0.75, "reset_time": future},
            },
        }
        self.assertEqual(statusline.quota_label(data, now), "x?]0;owned? 25% used")

    def test_empty_or_invalid_quota_hides_segment(self):
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        for quota in (None, [], "invalid", {}, {"": {"remaining_fraction": 0.5}}):
            with self.subTest(quota=quota):
                self.assertIsNone(statusline.quota_label({"quota": quota}, now))


class EndToEndTests(unittest.TestCase):
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
        self.env["GIT_CEILING_DIRECTORIES"] = str(self.root)
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
                "workspace": {"current_dir": str(cwd), "project_dir": str(cwd)},
                "cwd": str(cwd),
                "product": "antigravity",
                **data,
            }),
            env=self.env, check=True, capture_output=True, text=True, timeout=30,
        )
        host = statusline.host_label(socket.gethostname())
        prefix = f"{host} | " if host else ""
        self.assertTrue(result.stdout.startswith(prefix), result.stdout)
        return result.stdout[len(prefix):]

    def test_full_payload_renders_all_segments_in_order(self):
        now = datetime.now(timezone.utc)
        future = (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        home = os.path.expanduser("~")
        expected_folder = statusline.folder(str(self.project), home, statusline.scratch_roots(home))
        output = self.render(
            self.project,
            model={
                "id": "gemini-4-neon-high",
                "display_name": "Gemini 4 Neon (High)",
                "effort": "high",
            },
            email="developer@example.com",
            context_window={
                "context_window_size": 1048576,
                "used_percentage": 14.24,
                "current_usage": {"input_tokens": 63382},
            },
            quota={
                "gemini-weekly": {
                    "remaining_fraction": 0.9378,
                    "reset_time": future,
                    "reset_in_seconds": 172800,
                },
            },
        )
        self.assertEqual(
            output,
            f"{expected_folder} | 🌿 main | 🤖 Gemini 4 Neon (High) | ⚙ developer@example.com | ctx 14% | gemini-weekly 6% used\n",
        )

    def test_worktrees_and_detached_head(self):
        named = self.worktree(self.project, "feature", "feature")
        (named / "src").mkdir()
        other = self.worktree(self.project, "checkout-2", "topic")
        self.assertEqual(self.render(named / "src"), segment("🌳", named / "src", "project") + " | 🌿 feature\n")
        self.assertEqual(self.render(other), segment("🌳", other, "project/checkout-2") + " | 🌿 topic\n")
        self.git("-C", str(self.project), "switch", "--quiet", "--detach", "main")
        commit = subprocess.run(
            ["git", "-C", str(self.project), "rev-parse", "--short", "HEAD"],
            env=self.env, check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        home = os.path.expanduser("~")
        expected_folder = statusline.folder(str(self.project), home, statusline.scratch_roots(home))
        self.assertEqual(self.render(self.project), f"{expected_folder} | 🌿 ({commit})\n")

    def test_invalid_or_empty_stdin_exits_cleanly_without_output(self):
        for payload in ("", "{", "[]", "null"):
            with self.subTest(payload=payload):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT)],
                    input=payload,
                    env=self.env, check=True, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.ansible_safe_run import (
    UnsafePreview,
    audit,
    inspect_preview,
    main,
    preview_restarts,
)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.source = self.root / "source"
        self.source.write_text("keep this configuration\n")
        self.target = self.root / "target"
        self.ref = str(self.root / "playbook.yaml") + ":2"
        self.task = {"ansible.builtin.file": {"state": "link"}}
        self.result = {
            "action": "ansible.builtin.file",
            "changed": True,
            "src": str(self.source),
            "diff": {
                "before": {"path": str(self.target), "state": "absent"},
                "after": {"path": str(self.target), "state": "link"},
            },
        }

    def inspect(self, result=None, action="ansible.builtin.file", task=None):
        result = self.result if result is None else result
        plan = {
            "stats": {
                "127.0.0.1": {
                    "failures": 0,
                    "unreachable": 0,
                    "ignored": 0,
                    "rescued": 0,
                }
            },
            "plays": [
                {
                    "tasks": [
                        {"task": {"path": self.ref}, "hosts": {"127.0.0.1": result}}
                    ]
                }
            ],
        }
        return inspect_preview(plan, {self.ref: (action, task or self.task)}, {})

    def test_new_link_preview_does_not_create_target(self):
        snapshots, restarts = self.inspect()
        self.assertEqual(snapshots[str(self.target)], ("absent",))
        self.assertFalse(self.target.exists())
        self.assertEqual(restarts, set())

    def test_existing_file_cannot_be_overwritten(self):
        self.target.write_text("irreplaceable data")
        self.result["diff"]["before"]["state"] = "file"
        with self.assertRaisesRegex(UnsafePreview, "replace or remove"):
            self.inspect()
        self.assertEqual(self.target.read_text(), "irreplaceable data")

    def test_changed_symlink_target_is_rejected(self):
        self.target.symlink_to(self.source)
        self.result["diff"]["before"] = {"path": str(self.target), "src": "old-target"}
        self.result["diff"]["after"]["src"] = str(self.source)
        with self.assertRaisesRegex(UnsafePreview, "symlink target"):
            self.inspect()
        self.assertEqual(self.target.readlink(), self.source)

    def test_deletion_is_rejected(self):
        self.result["diff"]["after"]["state"] = "absent"
        with self.assertRaisesRegex(UnsafePreview, "replace or remove"):
            self.inspect()

    def test_incomplete_diff_is_rejected(self):
        del self.result["diff"]["before"]
        with self.assertRaisesRegex(UnsafePreview, "before/after path"):
            self.inspect()

    def test_missing_source_is_rejected(self):
        self.result["src"] = str(self.root / "unmaterialized-clone")
        with self.assertRaisesRegex(UnsafePreview, "source does not exist"):
            self.inspect()

    def test_unplanned_parent_directory_is_rejected(self):
        target = self.root / "missing-parent" / "target"
        self.result["diff"]["before"]["path"] = str(target)
        self.result["diff"]["after"]["path"] = str(target)
        with self.assertRaisesRegex(UnsafePreview, "parent directory"):
            self.inspect()

    def test_destination_drift_is_rejected(self):
        self.target.write_text("appeared during preview")
        with self.assertRaisesRegex(UnsafePreview, "destination appeared"):
            self.inspect()

    def test_incomplete_loop_is_rejected(self):
        result = {
            "action": "ansible.builtin.file",
            "changed": True,
            "results": [self.result],
        }
        with self.assertRaisesRegex(UnsafePreview, "Incomplete loop"):
            self.inspect(result, task={**self.task, "loop": ["first", "omitted"]})

    def test_unsupported_skip_is_rejected(self):
        self.result.update(skipped=True, msg="module does not support check mode")
        with self.assertRaisesRegex(UnsafePreview, "proven conditional skip"):
            self.inspect()

    def test_new_clone_is_incomplete(self):
        with self.assertRaisesRegex(UnsafePreview, "materialized source"):
            self.inspect(
                {"action": "ansible.builtin.git", "changed": True},
                "ansible.builtin.git",
            )

    def test_omitted_selected_task_is_rejected(self):
        with self.assertRaises(UnsafePreview):
            inspect_preview(
                {
                    "stats": {
                        "127.0.0.1": {
                            "failures": 0,
                            "unreachable": 0,
                            "ignored": 0,
                            "rescued": 0,
                        }
                    },
                    "plays": [{"tasks": []}],
                },
                {self.ref: ("ansible.builtin.file", self.task)},
                {},
            )

    def test_unknown_command_is_rejected_before_check_mode(self):
        path = self.root / "unsafe.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Dangerous preview\n      ansible.builtin.command: rm -rf /important-data\n      check_mode: false\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_playbook_import_is_rejected_before_check_mode(self):
        path = self.root / "import.yaml"
        path.write_text("- import_playbook: unreviewed.yaml\n")
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unaudited playbook"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_task_args_cannot_bypass_module_audit(self):
        path = self.root / "args.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Hidden file arguments\n"
            "      ansible.builtin.file:\n        path: /tmp/target\n"
            "        state: link\n      args:\n        force: true\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unknown task controls"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_string_tags_select_the_complete_tag(self):
        path = self.root / "tags.yaml"
        path.write_text(
            "- hosts: all\n  tags: system\n  tasks:\n"
            "    - name: New directory\n      ansible.builtin.file:\n"
            "        path: /tmp/preview-only\n        state: directory\n"
            "      tags: files\n"
        )
        expected, _, _ = audit(path, {"files"}, set())
        self.assertEqual(len(expected), 1)

    def test_free_form_git_arguments_fail_closed(self):
        path = self.root / "git.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Clone\n"
            "      ansible.builtin.git: repo=https://example.invalid dest=/tmp/repo\n"
        )
        with self.assertRaisesRegex(UnsafePreview, "Git check mode"):
            audit(path, {"all"}, set())

    def test_extra_vars_cannot_disable_check_mode(self):
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main(["ansible/playbook-macos.yaml", "-e", "ansible_check_mode=false"])
            run.assert_not_called()

    def test_check_mode_condition_cannot_hide_apply_effects(self):
        path = self.root / "hidden.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Hidden operation\n      ansible.builtin.file:\n        path: /important-data\n        state: directory\n      when: not ansible_check_mode\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_guard_blocks_apply_when_preview_fails(self):
        with patch(
            "scripts.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", ""),
        ) as run:
            with self.assertRaises(UnsafePreview):
                main(["ansible/playbook-macos.yaml"])
            self.assertEqual(run.call_count, 1)
            self.assertIn("--check", run.call_args.args[0])
            self.assertIn("--diff", run.call_args.args[0])

    def safe_directory_plan(self):
        path = self.root / "safe.yaml"
        path.write_text(
            f"- hosts: all\n  tasks:\n    - name: Create a new test directory\n      ansible.builtin.file:\n        path: {self.target}\n        state: directory\n"
        )
        expected, _, _ = audit(path, {"all"}, set())
        ref = next(iter(expected))
        result = {
            "action": "ansible.builtin.file",
            "changed": True,
            "diff": {
                "before": {"path": str(self.target), "state": "absent"},
                "after": {"path": str(self.target), "state": "directory"},
            },
        }
        plan = {
            "stats": {
                "127.0.0.1": {
                    "failures": 0,
                    "unreachable": 0,
                    "ignored": 0,
                    "rescued": 0,
                }
            },
            "plays": [
                {"tasks": [{"task": {"path": ref}, "hosts": {"127.0.0.1": result}}]}
            ],
        }
        return path, json.dumps(plan)

    def test_apply_follows_complete_preview_with_identical_selection(self):
        path, preview = self.safe_directory_plan()
        with patch(
            "scripts.ansible_safe_run.subprocess.run",
            side_effect=[
                subprocess.CompletedProcess([], 0, preview, ""),
                subprocess.CompletedProcess([], 0),
            ],
        ) as run:
            self.assertEqual(main([str(path)]), 0)
            check, apply = [call.args[0] for call in run.call_args_list]
            self.assertEqual(check[:-2], apply)
            self.assertEqual(check[-2:], ["--check", "--diff"])

    def test_config_drift_after_preview_blocks_apply(self):
        path, preview = self.safe_directory_plan()

        def drift(*args, **kwargs):
            path.write_text(path.read_text() + "# Configuration changed\n")
            return subprocess.CompletedProcess([], 0, preview, "")

        with patch("scripts.ansible_safe_run.subprocess.run", side_effect=drift) as run:
            with self.assertRaises(UnsafePreview):
                main([str(path)])
            self.assertEqual(run.call_count, 1)

    def test_restart_preview_sends_no_signal(self):
        with patch("scripts.ansible_safe_run.sys.platform", "darwin"), patch(
            "scripts.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", ""),
        ) as run:
            preview_restarts({"Finder", "SystemUIServer"})
            self.assertEqual(
                [call.args[0] for call in run.call_args_list],
                [
                    ["/usr/bin/killall", "-s", "Finder"],
                    ["/usr/bin/killall", "-s", "SystemUIServer"],
                ],
            )

    def handler_plan(self, command):
        handler_ref = str(self.root / "handlers.yaml") + ":2"
        result = {
            "action": "ansible.builtin.command",
            "changed": False,
            "skipped": True,
            "msg": "Command would have run if not in check mode",
            "cmd": command,
        }
        plan = {
            "stats": {
                "127.0.0.1": {
                    "failures": 0,
                    "unreachable": 0,
                    "ignored": 0,
                    "rescued": 0,
                }
            },
            "plays": [
                {
                    "tasks": [
                        {
                            "task": {"path": self.ref},
                            "hosts": {"127.0.0.1": self.result},
                        },
                        {"task": {"path": handler_ref}, "hosts": {"127.0.0.1": result}},
                    ]
                }
            ],
        }
        handlers = {
            handler_ref: (
                "ansible.builtin.command",
                {"ansible.builtin.command": "/usr/bin/killall Finder"},
            )
        }
        return plan, handlers

    def test_known_skipped_handler_requires_its_equivalent_preview(self):
        plan, handlers = self.handler_plan(["/usr/bin/killall", "Finder"])
        _, restarts = inspect_preview(
            plan, {self.ref: ("ansible.builtin.file", self.task)}, handlers
        )
        self.assertEqual(restarts, {"Finder"})

    def test_skipped_handler_command_must_match_audited_target(self):
        plan, handlers = self.handler_plan(["/usr/bin/killall", "unreviewed-process"])
        with self.assertRaisesRegex(UnsafePreview, "Restart handler"):
            inspect_preview(
                plan, {self.ref: ("ansible.builtin.file", self.task)}, handlers
            )

    def test_repository_playbooks_are_audited(self):
        for name in ("macos", "ubuntu-linux"):
            expected, _, _ = audit(
                Path(f"ansible/playbook-{name}.yaml"), {"all"}, set()
            )
            self.assertGreater(len(expected), 5)
        with self.assertRaises(UnsafePreview):
            audit(Path("ansible/playbook-arch-linux-vm.yaml"), {"all"}, set())


if __name__ == "__main__":
    unittest.main()

import json
import os
import sysconfig
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.ansible_safe_run import (
    UnsafePreview,
    audit,
    fingerprint,
    inspect_preview,
    main,
    preview_restarts,
    selected,
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

    def test_symlink_retargeted_during_preview_is_rejected(self):
        other = self.root / "other-source"
        other.write_text("unexpected target")
        self.target.symlink_to(other)
        self.result["diff"]["before"]["state"] = "link"
        with self.assertRaisesRegex(UnsafePreview, "Symlink target changed during preview"):
            self.inspect()
        self.assertEqual(self.target.readlink(), other)

    def test_deletion_is_rejected(self):
        self.result["diff"]["after"]["state"] = "absent"
        with self.assertRaisesRegex(UnsafePreview, "replace or remove"):
            self.inspect()

    def test_conflicting_planned_states_cannot_replace_a_created_directory(self):
        link_ref = str(self.root / "playbook.yaml") + ":6"
        directory = {
            "action": "ansible.builtin.file",
            "changed": True,
            "diff": {
                "before": {"path": str(self.target), "state": "absent"},
                "after": {"path": str(self.target), "state": "directory"},
            },
        }
        plan = {
            "stats": {"127.0.0.1": {"failures": 0, "unreachable": 0, "ignored": 0, "rescued": 0}},
            "plays": [{"tasks": [
                {"task": {"path": self.ref}, "hosts": {"127.0.0.1": directory}},
                {"task": {"path": link_ref}, "hosts": {"127.0.0.1": self.result}},
            ]}],
        }
        expected = {
            self.ref: ("ansible.builtin.file", {"ansible.builtin.file": {"state": "directory"}}),
            link_ref: ("ansible.builtin.file", self.task),
        }
        with self.assertRaisesRegex(UnsafePreview, "Conflicting planned file states"):
            inspect_preview(plan, expected, {})

    def test_planned_parent_snapshots_intermediate_symlink_ancestors(self):
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(first)
        directory = alias / "new-parent"
        target = directory / "link"
        link_ref = str(self.root / "playbook.yaml") + ":6"
        directory_result = {
            "action": "ansible.builtin.file", "changed": True,
            "diff": {"before": {"path": str(directory), "state": "absent"},
                     "after": {"path": str(directory), "state": "directory"}},
        }
        link_result = {
            "action": "ansible.builtin.file", "changed": True, "src": str(self.source),
            "diff": {"before": {"path": str(target), "state": "absent"},
                     "after": {"path": str(target), "state": "link"}},
        }
        plan = {
            "stats": {"127.0.0.1": {"failures": 0, "unreachable": 0, "ignored": 0, "rescued": 0}},
            "plays": [{"tasks": [
                {"task": {"path": self.ref}, "hosts": {"127.0.0.1": directory_result}},
                {"task": {"path": link_ref}, "hosts": {"127.0.0.1": link_result}},
            ]}],
        }
        expected = {
            self.ref: ("ansible.builtin.file", {"ansible.builtin.file": {"state": "directory"}}),
            link_ref: ("ansible.builtin.file", self.task),
        }
        snapshots, _ = inspect_preview(plan, expected, {})
        self.assertEqual(snapshots[str(directory)], ("absent",))
        self.assertEqual(snapshots[str(target)], ("absent",))
        alias.unlink()
        alias.symlink_to(second)
        self.assertNotEqual(fingerprint(alias), snapshots[str(alias)])

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

    def test_conditional_task_import_is_rejected_before_check_mode(self):
        path = self.root / "conditional-import.yaml"
        child = self.root / "child.yaml"
        child.write_text(
            "- name: New directory\n  ansible.builtin.file:\n"
            "    path: /tmp/preview-only\n    state: directory\n"
        )
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Import conditionally\n"
            "      ansible.builtin.import_tasks: child.yaml\n"
            "      when: approved_for_apply\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "condition"):
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
            "- hosts: all\n  gather_facts: false\n  tags: system\n  tasks:\n"
            "    - name: New directory\n      ansible.builtin.file:\n"
            "        path: /tmp/preview-only\n        state: directory\n"
            "      tags: files\n"
        )
        expected, _, _ = audit(path, {"files"}, set())
        self.assertEqual(len(expected), 1)

    def test_special_tags_and_skip_tags_match_ansible_selection(self):
        self.assertTrue(selected({"always"}, {"files"}, set()))
        self.assertFalse(selected({"always"}, {"files"}, {"always"}))
        self.assertFalse(selected({"never"}, {"all"}, set()))
        self.assertTrue(selected({"never"}, {"never"}, set()))
        self.assertTrue(selected({"files"}, {"files"}, set()))
        self.assertFalse(selected({"files"}, {"files"}, {"files"}))

    def test_directory_contents_do_not_change_its_entry_identity(self):
        before = fingerprint(self.root)
        (self.root / "unrelated-entry").write_text("updated elsewhere")
        self.assertEqual(fingerprint(self.root), before)

    def test_task_privilege_escalation_is_rejected_before_preview(self):
        path = self.root / "become.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Privileged file\n"
            "      ansible.builtin.file:\n        path: /tmp/target\n"
            "        state: directory\n      become: true\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unknown task controls"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_malformed_extra_vars_cannot_reach_preview(self):
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main(["ansible/playbook-macos.yaml", "--check", "-e", "[true]"])
            run.assert_not_called()

    def test_foreign_target_python_cannot_run_during_preview(self):
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "active Python environment"):
                main([
                    "ansible/playbook-macos.yaml", "--check", "-e",
                    "ansible_python_interpreter=/tmp/foreign-python",
                ])
            run.assert_not_called()

    def test_free_form_git_arguments_fail_closed(self):
        path = self.root / "git.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Clone\n"
            "      ansible.builtin.git: repo=https://example.invalid dest=/tmp/repo\n"
            "      when:\n        - clone_dotfiles | default(true) | bool\n"
        )
        with self.assertRaisesRegex(UnsafePreview, "Git check mode"):
            audit(path, {"all"}, set(), {"clone_dotfiles": "false"})

    def test_check_mode_template_cannot_choose_an_apply_only_target(self):
        path = self.root / "mode-target.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Unstable target\n"
            "      ansible.builtin.file:\n"
            "        path: \"{{ '/tmp/safe' if ansible_check_mode else '/tmp/victim' }}\"\n"
            "        state: directory\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Check-mode-dependent"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_dynamic_play_source_cannot_change_between_preview_and_apply(self):
        path = self.root / "dynamic-source.yaml"
        path.write_text(
            "- hosts: all\n  vars:\n"
            "    dotfiles_dir: \"{{ lookup('env', 'TARGET') }}\"\n"
            "  tasks:\n    - name: New directory\n"
            "      ansible.builtin.file:\n"
            "        path: /tmp/preview-only\n        state: directory\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "source and interpreter"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_conditional_link_after_stat_is_rejected_before_preview(self):
        path = self.root / "conditional.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n"
            "    - name: Create directory\n      ansible.builtin.file:\n"
            "        path: /tmp/new-parent\n        state: directory\n"
            "    - name: Recheck parent\n      ansible.builtin.stat:\n"
            "        path: /tmp/new-parent\n      register: parent_state\n"
            "    - name: Link conditionally\n      ansible.builtin.file:\n"
            "        path: /tmp/new-parent/link\n        src: /tmp/source\n"
            "        state: link\n      when: parent_state.stat.exists\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "condition"):
                main([str(path), "--check"])
            run.assert_not_called()

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

    def test_bare_condition_lookup_cannot_run_during_preview(self):
        path = self.root / "lookup.yaml"
        path.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Read state\n      ansible.builtin.stat:\n"
            "        path: /tmp/preview-only\n"
            "      when: lookup('pipe', 'touch /tmp/should-not-run')\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unaudited task condition"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_jinja_block_cannot_run_during_preview(self):
        path = self.root / "block.yaml"
        path.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: \"{% set x = lookup('pipe', 'touch /tmp/should-not-run') %} Hidden\"\n"
            "      ansible.builtin.stat:\n        path: /tmp/preview-only\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unaudited Jinja blocks"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_guard_blocks_apply_when_preview_fails(self):
        path, _ = self.safe_directory_plan()
        with patch(
            "scripts.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", ""),
        ) as run:
            with self.assertRaises(UnsafePreview):
                main([str(path)])
            self.assertEqual(run.call_count, 1)
            self.assertIn("--check", run.call_args.args[0])
            self.assertIn("--diff", run.call_args.args[0])

    def test_implicit_fact_gathering_is_rejected_before_preview(self):
        path = self.root / "implicit-facts.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: New directory\n"
            "      ansible.builtin.file:\n"
            "        path: /tmp/preview-only\n        state: directory\n"
        )
        with patch("scripts.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Implicit fact gathering"):
                main([str(path), "--check"])
            run.assert_not_called()

    def safe_directory_plan(self):
        path = self.root / "safe.yaml"
        path.write_text(
            f"- hosts: all\n  gather_facts: false\n  tasks:\n    - name: Create a new test directory\n      ansible.builtin.file:\n        path: {self.target}\n        state: directory\n"
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

    def test_diff_shows_target_without_exposing_ansible_values(self):
        path, preview = self.safe_directory_plan()
        plan = json.loads(preview)
        plan["plays"][0]["tasks"][0]["hosts"]["127.0.0.1"]["diff"]["secret"] = "private-value"
        output = StringIO()
        with patch(
            "scripts.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(plan), ""),
        ), redirect_stdout(output):
            self.assertEqual(main([str(path), "--check", "--diff"]), 0)
        self.assertIn(f"Would create directory: {self.target}", output.getvalue())
        self.assertNotIn("private-value", output.getvalue())

    def test_config_drift_after_preview_blocks_apply(self):
        path, preview = self.safe_directory_plan()

        def drift(*args, **kwargs):
            path.write_text(path.read_text() + "# Configuration changed\n")
            return subprocess.CompletedProcess([], 0, preview, "")

        with patch("scripts.ansible_safe_run.subprocess.run", side_effect=drift) as run:
            with self.assertRaises(UnsafePreview):
                main([str(path)])
            self.assertEqual(run.call_count, 1)

    def test_inherited_ansible_and_python_plugins_are_removed(self):
        path, preview = self.safe_directory_plan()
        with patch.dict(os.environ, {"ANSIBLE_LIBRARY": "/tmp/foreign", "ANSIBLE_FILTER_PLUGINS": "/tmp/foreign", "PYTHONPATH": "/tmp/foreign"}), patch(
            "scripts.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, preview, ""),
        ) as run:
            self.assertEqual(main([str(path), "--check"]), 0)
        environment = run.call_args.kwargs["env"]
        installed = Path(sysconfig.get_path("purelib")).resolve()
        self.assertEqual(environment["ANSIBLE_LIBRARY"], str(installed / "ansible/modules"))
        self.assertEqual(environment["ANSIBLE_FILTER_PLUGINS"], str(installed / "ansible/plugins/filter"))
        self.assertIn("dotfiles-ansible-home-", environment["ANSIBLE_HOME"])
        self.assertEqual(environment["ANSIBLE_VARS_ENABLED"], "")
        self.assertNotIn("PYTHONPATH", environment)
        self.assertEqual(environment["ANSIBLE_COLLECTIONS_SCAN_SYS_PATH"], "False")

    def test_adjacent_group_vars_cannot_run_a_template_during_preview(self):
        playbook = self.root / "playbook.yaml"
        playbook.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Gather safe facts\n      ansible.builtin.setup:\n"
            "        fact_path: /dev/null\n"
            "    - name: Inspect home directory\n      ansible.builtin.file:\n"
            "        path: \"{{ dotfiles_home | default(ansible_facts['user_dir']) }}\"\n"
            "        state: directory\n"
        )
        marker = self.root / "injected"
        group_vars = self.root / "group_vars"
        group_vars.mkdir()
        (group_vars / "all.yaml").write_text(
            f'dotfiles_home: "{{{{ lookup(\'pipe\', \'/usr/bin/touch {marker}\') }}}}"\n'
        )
        self.assertEqual(main([str(playbook), "--check"]), 0)
        self.assertFalse(marker.exists())

    def test_preference_drift_after_preview_blocks_apply(self):
        path = self.root / "preference.yaml"
        path.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n    - name: Set preference\n"
            "      community.general.osx_defaults:\n"
            "        domain: test.domain\n        key: SafeFlag\n"
            "        type: bool\n        value: true\n"
        )
        ref = str(path) + ":4"
        plan = {
            "stats": {"127.0.0.1": {"failures": 0, "unreachable": 0, "ignored": 0, "rescued": 0}},
            "plays": [{"tasks": [{"task": {"path": ref}, "hosts": {"127.0.0.1": {"action": "community.general.osx_defaults", "changed": True}}}]}],
        }
        with patch(
            "scripts.ansible_safe_run.subprocess.run",
            side_effect=[
                subprocess.CompletedProcess([], 0, "0", ""),
                subprocess.CompletedProcess([], 0, json.dumps(plan), ""),
                subprocess.CompletedProcess([], 0, "0", ""),
                subprocess.CompletedProcess([], 0, "1", ""),
            ],
        ) as run:
            with self.assertRaisesRegex(UnsafePreview, "preference state changed after preview"):
                main([str(path)])
        self.assertEqual(run.call_count, 4)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/defaults", "read", "test.domain", "SafeFlag"])

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
                Path(f"ansible/playbook-{name}.yaml"),
                {"all"},
                set(),
                {"clone_dotfiles": "false"},
            )
            self.assertGreater(len(expected), 5)
        with self.assertRaises(UnsafePreview):
            audit(Path("ansible/playbook-arch-linux-vm.yaml"), {"all"}, set())


if __name__ == "__main__":
    unittest.main()

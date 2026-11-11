import json
import os
import sys
import sysconfig
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import platform
import signal
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts.deploy import ansible_safe_run as safe_run
from scripts.deploy.ansible_safe_run import (
    UnsafePreview,
    audit,
    exit_on_termination,
    fingerprint,
    inspect_preview,
    main,
    preview_restarts,
    selected,
)


ansible_run = getattr(safe_run, "run_ansible", None)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class PreviewTests(unittest.TestCase):
    def setUp(self):
        # Route Ansible runs through each test's subprocess.run stub, in order
        # with the preference reads; the termination test runs the real helper.
        ansible = patch(
            "scripts.deploy.ansible_safe_run.run_ansible",
            side_effect=lambda command, **kwargs: safe_run.subprocess.run(
                command, **kwargs
            ),
        )
        ansible.start()
        self.addCleanup(ansible.stop)
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

    def test_previewed_directory_cannot_become_a_symlink(self):
        self.target.symlink_to(self.root)
        result = {
            "action": "ansible.builtin.file",
            "changed": False,
            "diff": {
                "before": {"path": str(self.target), "state": "directory"},
                "after": {"path": str(self.target), "state": "directory"},
            },
        }
        with self.assertRaisesRegex(UnsafePreview, "directory changed type"):
            self.inspect(result, task={"ansible.builtin.file": {"state": "directory"}})

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

    def test_planned_symlink_cannot_redirect_descendant_task(self):
        source_dir = self.root / "existing-directory"
        source_dir.mkdir()
        alias = self.root / "alias"
        child = alias / "new-directory"
        child_ref = str(self.root / "playbook.yaml") + ":6"
        link_result = {
            "action": "ansible.builtin.file", "changed": True, "src": str(source_dir),
            "diff": {"before": {"path": str(alias), "state": "absent"},
                     "after": {"path": str(alias), "state": "link"}},
        }
        child_result = {
            "action": "ansible.builtin.file", "changed": True,
            "diff": {"before": {"path": str(child), "state": "absent"},
                     "after": {"path": str(child), "state": "directory"}},
        }
        cases = [
            (self.ref, link_result, self.task),
            (child_ref, child_result, {"ansible.builtin.file": {"state": "directory"}}),
        ]
        for ordered in (cases, list(reversed(cases))):
            plan = {
                "stats": {"127.0.0.1": {"failures": 0, "unreachable": 0, "ignored": 0, "rescued": 0}},
                "plays": [{"tasks": [
                    {"task": {"path": ref}, "hosts": {"127.0.0.1": result}}
                    for ref, result, _ in ordered
                ]}],
            }
            expected = {ref: ("ansible.builtin.file", task) for ref, _, task in cases}
            with self.assertRaisesRegex(UnsafePreview, "Planned symlink"):
                inspect_preview(plan, expected, {})

    def test_alias_parents_cannot_plan_different_links_to_one_destination(self):
        directory = self.root / "actual"
        directory.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(directory)
        other = self.root / "other-source"
        other.write_text("other\n")
        second_ref = str(self.root / "playbook.yaml") + ":6"
        def item(path, source):
            return {
                "action": "ansible.builtin.file", "changed": True, "src": str(source),
                "diff": {"before": {"path": str(path), "state": "absent"},
                         "after": {"path": str(path), "state": "link"}},
            }
        plan = {
            "stats": {"127.0.0.1": {"failures": 0, "unreachable": 0, "ignored": 0, "rescued": 0}},
            "plays": [{"tasks": [
                {"task": {"path": self.ref}, "hosts": {"127.0.0.1": item(directory / "link", self.source)}},
                {"task": {"path": second_ref}, "hosts": {"127.0.0.1": item(alias / "link", other)}},
            ]}],
        }
        expected = {
            self.ref: ("ansible.builtin.file", self.task),
            second_ref: ("ansible.builtin.file", self.task),
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_playbook_import_is_rejected_before_check_mode(self):
        path = self.root / "import.yaml"
        path.write_text("- import_playbook: unreviewed.yaml\n")
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unknown task controls"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_recursive_file_task_is_rejected_before_preview(self):
        path = self.root / "recursive.yaml"
        path.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Recurse into existing directory\n"
            "      ansible.builtin.file:\n"
            f"        path: {self.root}\n"
            "        state: directory\n        recurse: true\n"
        )
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Recursive file changes"):
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
        self.assertTrue(selected(set(), {"untagged"}, set()))
        self.assertFalse(selected(set(), {"all"}, {"untagged"}))
        self.assertFalse(selected({"files"}, {"all"}, {"tagged"}))
        self.assertTrue(selected({"always"}, {"all"}, {"all"}))
        self.assertFalse(selected({"files"}, {"all"}, {"all"}))
        self.assertFalse(selected({"never"}, {"tagged"}, set()))

    def test_repeated_tag_flags_are_combined_for_audit_and_ansible(self):
        path, preview = self.safe_directory_plan()
        with patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, preview, ""),
        ) as run:
            self.assertEqual(main([
                str(path), "--check", "--tags", "all", "--tags", "untagged",
                "--skip-tags", "files", "--skip-tags", "defaults",
            ]), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--tags") + 1], "all,untagged")
        self.assertEqual(command[command.index("--skip-tags") + 1], "files,defaults")
        path.write_text(path.read_text() + "      tags: files\n")
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "No selected tasks"):
                main([
                    str(path), "--check", "--tags", "all",
                    "--skip-tags", "files", "--skip-tags", "defaults",
                ])
            run.assert_not_called()

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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unknown task controls"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_malformed_extra_vars_cannot_reach_preview(self):
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main(["ansible/playbook-macos.yaml", "--check", "-e", "[true]"])
            run.assert_not_called()

    def test_foreign_target_python_cannot_run_during_preview(self):
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main([
                    "ansible/playbook-macos.yaml", "--check", "-e",
                    "ansible_python_interpreter=/tmp/foreign-python",
                ])
            run.assert_not_called()

    def test_sibling_virtualenv_python_cannot_run_during_preview(self):
        interpreter = self.root / "other-venv" / "bin" / "python3"
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(Path(sysconfig.get_path("scripts")) / "python3")
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main([
                    "ansible/playbook-macos.yaml", "--check", "-e",
                    f"ansible_python_interpreter={interpreter}",
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "condition"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_extra_vars_cannot_disable_check_mode(self):
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaises(UnsafePreview):
                main(["ansible/playbook-macos.yaml", "-e", "ansible_check_mode=false"])
            run.assert_not_called()

    def test_check_mode_condition_cannot_hide_apply_effects(self):
        path = self.root / "hidden.yaml"
        path.write_text(
            "- hosts: all\n  tasks:\n    - name: Hidden operation\n      ansible.builtin.file:\n        path: /important-data\n        state: directory\n      when: not ansible_check_mode\n"
        )
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Unaudited Jinja blocks"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_preference_binary_override_cannot_run_during_preview(self):
        path = self.root / "custom-defaults.yaml"
        path.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Change preference\n      community.general.osx_defaults:\n"
            "        domain: test.domain\n        key: SafeFlag\n"
            "        type: bool\n        value: true\n"
            "        path: /tmp/unaudited-defaults\n"
        )
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "in-place boolean"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_play_name_lookup_cannot_run_during_preview(self):
        path = self.root / "play-name.yaml"
        path.write_text(
            "- name: \"{{ lookup('pipe', 'touch /tmp/should-not-run') }}\"\n"
            "  hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Read state\n      ansible.builtin.stat:\n"
            "        path: /tmp/preview-only\n"
        )
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Play names"):
                main([str(path), "--check"])
            run.assert_not_called()

    def test_guard_blocks_apply_when_preview_fails(self):
        path, _ = self.safe_directory_plan()
        with patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
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
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
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
            "scripts.deploy.ansible_safe_run.subprocess.run",
            side_effect=[
                subprocess.CompletedProcess([], 0, preview, ""),
                subprocess.CompletedProcess([], 0),
            ],
        ) as run:
            self.assertEqual(main([str(path)]), 0)
            check, apply = [call.args[0] for call in run.call_args_list]
            self.assertEqual(check[:-2], apply)
            self.assertEqual(check[-2:], ["--check", "--diff"])
            variables = json.loads(apply[apply.index("-e") + 1])
            self.assertEqual(variables, {
                "dotfiles_dir": str(Path.cwd()),
                "clone_dotfiles": False,
                "ansible_python_interpreter": sys.executable,
            })

    def test_explicit_extra_vars_override_checkout_defaults_in_order(self):
        path, preview = self.safe_directory_plan()
        source = self.root / "checkout with spaces"
        source.mkdir()
        with patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, preview, ""),
        ) as run:
            self.assertEqual(main([
                str(path), "--check", "-e", "dotfiles_dir=/unused-checkout",
                "-e", json.dumps({"dotfiles_dir": str(source), "clone_dotfiles": False}),
                "-e", f"dotfiles_home={self.target} clone_dotfiles=false",
            ]), 0)
        command = run.call_args.args[0]
        variables = json.loads(command[command.index("-e") + 1])
        self.assertEqual(variables, {
            "dotfiles_dir": str(source),
            "clone_dotfiles": "false",
            "ansible_python_interpreter": sys.executable,
            "dotfiles_home": str(self.target),
        })

    def test_explicit_clone_cannot_bypass_guard(self):
        for name in ("ubuntu-linux", "arch-linux"):
            for value in ("clone_dotfiles=true", '{"clone_dotfiles": true}'):
                for tags in ([], ["--tags", "files"]):
                    with self.subTest(playbook=name, value=value, tags=tags), patch(
                        "scripts.deploy.ansible_safe_run.subprocess.run",
                    ) as run:
                        with self.assertRaisesRegex(UnsafePreview, "Conditional clone"):
                            main([f"ansible/playbook-{name}.yaml", "--check", "-e", value, *tags])
                        run.assert_not_called()

    def test_diff_shows_target_without_exposing_ansible_values(self):
        path, preview = self.safe_directory_plan()
        plan = json.loads(preview)
        plan["plays"][0]["tasks"][0]["hosts"]["127.0.0.1"]["diff"]["secret"] = "private-value"
        output = StringIO()
        with patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
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

        with patch("scripts.deploy.ansible_safe_run.subprocess.run", side_effect=drift) as run:
            with self.assertRaises(UnsafePreview):
                main([str(path)])
            self.assertEqual(run.call_count, 1)

    def test_playbook_symlink_retarget_after_preview_blocks_apply(self):
        path, preview = self.safe_directory_plan()
        alias = self.root / "selected.yaml"
        other = self.root / "other.yaml"
        other.write_text(path.read_text())
        alias.symlink_to(path)

        def retarget(*args, **kwargs):
            alias.unlink()
            alias.symlink_to(other)
            return subprocess.CompletedProcess([], 0, preview, "")

        with patch("scripts.deploy.ansible_safe_run.subprocess.run", side_effect=retarget) as run:
            with self.assertRaisesRegex(UnsafePreview, "Configuration or target state changed"):
                main([str(alias)])
            self.assertEqual(run.call_count, 1)

    def test_controller_python_allows_preview_without_apply(self):
        path, preview = self.safe_directory_plan()
        with patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, preview, ""),
        ) as run:
            self.assertEqual(main([
                str(path), "--check", "-e",
                f"ansible_python_interpreter={sys.executable}",
            ]), 0)
            self.assertEqual(run.call_count, 1)
            self.assertFalse(self.target.exists())

    def test_controller_symlink_retarget_after_preview_blocks_apply(self):
        path, preview = self.safe_directory_plan()
        interpreter = self.root / "controller-python"
        interpreter.symlink_to(sys.executable)

        def retarget(*args, **kwargs):
            interpreter.unlink()
            interpreter.symlink_to(self.source)
            return subprocess.CompletedProcess([], 0, preview, "")

        with patch("scripts.deploy.ansible_safe_run.sys.executable", str(interpreter)):
            with patch("scripts.deploy.ansible_safe_run.subprocess.run", side_effect=retarget) as run:
                with self.assertRaises(UnsafePreview):
                    main([str(path), "-e", f"ansible_python_interpreter={interpreter}"])
                self.assertEqual(run.call_count, 1)
                self.assertFalse(self.target.exists())

    def test_path_python_cannot_bypass_controller_environment(self):
        aliases = self.root / "ambient-python" / "bin"
        aliases.mkdir(parents=True)
        interpreter = aliases / "python3"
        interpreter.symlink_to(Path(sys.executable))
        with patch.dict(os.environ, {"PATH": str(aliases)}):
            with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
                with self.assertRaises(UnsafePreview):
                    main([
                        "ansible/playbook-macos.yaml", "--check", "-e",
                        f"ansible_python_interpreter={interpreter}",
                    ])
                run.assert_not_called()

    def test_inherited_ansible_and_python_plugins_are_removed(self):
        path, preview = self.safe_directory_plan()
        with patch.dict(os.environ, {"ANSIBLE_LIBRARY": "/tmp/foreign", "ANSIBLE_FILTER_PLUGINS": "/tmp/foreign", "PYTHONPATH": "/tmp/foreign", "PATH": f"{self.root}/shadow:/usr/bin"}), patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
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
        self.assertEqual(environment["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")
        self.assertEqual(environment["PYTHONNOUSERSITE"], "1")
        self.assertEqual(environment["PYTHONSAFEPATH"], "1")
        self.assertEqual(run.call_args.args[0][:3], [sys.executable, "-I", str(Path(sysconfig.get_path("scripts")).resolve() / "ansible-playbook")])

    def test_adjacent_group_vars_cannot_run_a_template_during_preview(self):
        playbook = self.root / "playbook.yaml"
        playbook.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Gather safe facts\n      ansible.builtin.setup:\n"
            "        fact_path: /dev/null\n"
            "        gather_subset: ['!all', '!min', 'distribution', 'user']\n"
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
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        collectors = [self.root / f"{name}-ran" for name in ("facter", "ohai", "uname", "defaults")]
        for name, effect in zip(("facter", "ohai", "uname", "defaults"), collectors, strict=True):
            executable = bin_dir / name
            executable.write_text(f"#!/bin/sh\n/usr/bin/touch {effect}\n")
            executable.chmod(0o755)
        with patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}):
            self.assertEqual(main([str(playbook), "--check"]), 0)
        self.assertFalse(marker.exists())
        self.assertTrue(all(not effect.exists() for effect in collectors))

    def test_playbook_local_plugin_is_rejected_before_preview(self):
        playbook = self.root / "playbook.yaml"
        playbook.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Inspect safe path\n      ansible.builtin.file:\n"
            f"        path: {self.target}\n        state: directory\n"
        )
        plugins = self.root / "filter_plugins"
        plugins.mkdir()
        (plugins / "unsafe.py").write_text("raise RuntimeError('plugin ran')\n")
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Playbook-local plugins"):
                main([str(playbook), "--check"])
            run.assert_not_called()

    def test_plugin_created_during_preview_blocks_apply(self):
        path, preview = self.safe_directory_plan()
        plugin = self.root / "collections"

        def create_plugin(*args, **kwargs):
            plugin.mkdir()
            return subprocess.CompletedProcess([], 0, preview, "")

        with patch("scripts.deploy.ansible_safe_run.subprocess.run", side_effect=create_plugin) as run:
            with self.assertRaisesRegex(UnsafePreview, "Playbook-local plugins"):
                main([str(path)])
            self.assertEqual(run.call_count, 1)

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
            "scripts.deploy.ansible_safe_run.subprocess.run",
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

    def test_conflicting_preference_writes_block_before_preview(self):
        path = self.root / "conflicting-preferences.yaml"
        path.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Enable preference\n"
            "      community.general.osx_defaults:\n"
            "        domain: test.domain\n        key: SafeFlag\n"
            "        type: bool\n        value: true\n"
            "    - name: Disable preference\n"
            "      community.general.osx_defaults:\n"
            "        domain: test.domain\n        key: SafeFlag\n"
            "        type: bool\n        value: false\n"
        )
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Conflicting planned macOS preference"):
                main([str(path)])
            run.assert_not_called()

    def dconf_playbook(self, task):
        path = self.root / "dconf.yaml"
        path.write_text(
            "- hosts: all\n  gather_facts: false\n  tasks:\n"
            "    - name: Set dconf key\n" + task
        )
        return path

    def test_dconf_key_needs_the_linux_mint_condition(self):
        for condition in ("", "      when: ansible_facts['os_family'] != 'Darwin'\n"):
            path = self.dconf_playbook(
                "      community.general.dconf:\n"
                "        key: /org/test/drag-threshold\n        value: '8'\n"
                + condition
            )
            with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
                with self.assertRaisesRegex(UnsafePreview, "Linux Mint fact"):
                    main([str(path), "--check"])
                run.assert_not_called()

    def test_dconf_reset_and_non_integer_values_are_rejected(self):
        for arguments in (
            "        key: /org/test/drag-threshold\n        state: absent\n",
            "        key: /org/test/drag-threshold\n        value: \"'x'\"\n",
            "        key: /org/test/\n        value: '8'\n",
            "        key: /org/test/drag-threshold\n        value: 8\n",
        ):
            path = self.dconf_playbook(
                "      community.general.dconf:\n" + arguments
                + "      when: ansible_facts['distribution'] == 'Linux Mint'\n"
            )
            with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
                with self.assertRaisesRegex(UnsafePreview, "integer dconf keys"):
                    main([str(path), "--check"])
                run.assert_not_called()

    def test_conflicting_dconf_writes_block_before_preview(self):
        key = "      community.general.dconf:\n        key: /org/test/drag-threshold\n"
        mint = "      when: ansible_facts['distribution'] == 'Linux Mint'\n"
        path = self.dconf_playbook(
            key + "        value: '8'\n" + mint
            + "    - name: Lower dconf key\n" + key + "        value: '1'\n" + mint
        )
        with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
            with self.assertRaisesRegex(UnsafePreview, "Conflicting planned dconf"):
                main([str(path)])
            run.assert_not_called()

    def test_skipped_dconf_key_is_a_proven_conditional_skip(self):
        result = {
            "action": "community.general.dconf",
            "changed": False,
            "skipped": True,
            "skip_reason": "Conditional result was False",
            "false_condition": "ansible_facts['distribution'] == 'Linux Mint'",
        }
        task = {"community.general.dconf": {"key": "/org/test/drag-threshold", "value": "8"}}
        self.assertEqual(
            self.inspect(result, "community.general.dconf", task), ({}, set())
        )

    def test_dconf_drift_after_preview_blocks_apply(self):
        path = self.dconf_playbook(
            "      community.general.dconf:\n"
            "        key: /org/test/drag-threshold\n        value: '8'\n"
            "      when: ansible_facts['distribution'] == 'Linux Mint'\n"
        )
        ref = str(path) + ":4"
        plan = {
            "stats": {"127.0.0.1": {"failures": 0, "unreachable": 0, "ignored": 0, "rescued": 0}},
            "plays": [{"tasks": [{"task": {"path": ref}, "hosts": {"127.0.0.1": {"action": "community.general.dconf", "changed": True}}}]}],
        }
        output = StringIO()
        with patch("scripts.deploy.ansible_safe_run.Path.is_file", return_value=True), patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
            side_effect=[
                subprocess.CompletedProcess([], 0, "1", ""),
                subprocess.CompletedProcess([], 0, json.dumps(plan), ""),
                subprocess.CompletedProcess([], 0, "1", ""),
                subprocess.CompletedProcess([], 0, "4", ""),
            ],
        ) as run, redirect_stdout(output):
            with self.assertRaisesRegex(UnsafePreview, "preference state changed after preview"):
                main([str(path), "--diff"])
        self.assertEqual(run.call_count, 4)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/dconf", "read", "/org/test/drag-threshold"])
        self.assertIn("Would update dconf key: /org/test/drag-threshold", output.getvalue())

    def test_restart_preview_sends_no_signal(self):
        with patch("scripts.deploy.ansible_safe_run.sys.platform", "darwin"), patch(
            "scripts.deploy.ansible_safe_run.subprocess.run",
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

    def test_termination_stops_ansible_and_removes_isolated_home(self):
        path, _ = self.safe_directory_plan()
        scripts, packages = self.root / "scripts", self.root / "packages"
        scripts.mkdir()
        # The fake controller forks a worker that ignores polite stops, as an
        # Ansible worker or module can, and reports both PIDs once it is ready.
        (scripts / "ansible-playbook").write_text(
            "import os, pathlib, subprocess, sys, time\n"
            "pid_file = pathlib.Path(os.environ['FAKE_ANSIBLE_PID'])\n"
            "ready = pid_file.with_suffix('.ready')\n"
            "worker = subprocess.Popen([sys.executable, '-c',\n"
            "    'import pathlib, signal, sys, time\\n'\n"
            "    'for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):\\n'\n"
            "    '    signal.signal(signum, signal.SIG_IGN)\\n'\n"
            "    'pathlib.Path(sys.argv[1]).touch()\\n'\n"
            "    'time.sleep(60)\\n', str(ready)])\n"
            "while not ready.exists():\n"
            "    time.sleep(0.01)\n"
            "pid_file.with_suffix('.tmp').write_text(f'{os.getpid()} {worker.pid}')\n"
            "pid_file.with_suffix('.tmp').rename(pid_file)\n"
            "time.sleep(60)\n"
        )
        for name in (
            "ansible/plugins/callback/default.py",
            "ansible_collections/ansible/posix/plugins/callback/json.py",
            "ansible_collections/community/general/plugins/modules/osx_defaults.py",
            "ansible_collections/community/general/plugins/modules/dconf.py",
        ):
            (packages / name).parent.mkdir(parents=True, exist_ok=True)
            (packages / name).write_text("")
        for directory in ("modules", *(f"plugins/{name}" for name in (
            "action", "become", "cache", "callback", "cliconf", "connection",
            "doc_fragments", "filter", "httpapi", "inventory", "lookup",
            "netconf", "shell", "strategy", "terminal", "test", "vars",
        ))):
            (packages / "ansible" / directory).mkdir(parents=True, exist_ok=True)
        # Run the real entry point with only the installed-Ansible location faked.
        driver = (
            "import runpy, sys, sysconfig\n"
            f"paths = {{'scripts': {str(scripts)!r}, 'purelib': {str(packages)!r}}}\n"
            "sysconfig.get_path = paths.__getitem__\n"
            "sys.argv = ['ansible_safe_run.py', sys.argv[1]]\n"
            "runpy.run_path('scripts/deploy/ansible_safe_run.py', run_name='__main__')\n"
        )
        # SIGINT reaches only the guard, as Ctrl-C does once Ansible runs in
        # its own process group.
        for number, signum in enumerate(
            (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
        ):
            status = 128 + signum
            with self.subTest(signal=signum.name):
                pid_file = self.root / f"ansible-{number}.pid"
                temporary = self.root / f"tmp-{number}"
                temporary.mkdir()
                wrapper = subprocess.Popen(
                    [sys.executable, "-c", driver, str(path)],
                    cwd=Path(__file__).resolve().parents[1],
                    env={
                        **os.environ,
                        "FAKE_ANSIBLE_PID": str(pid_file),
                        "TMPDIR": str(temporary),
                    },
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                children = []
                try:
                    deadline = time.monotonic() + 30
                    while not pid_file.exists():
                        if wrapper.poll() is not None or time.monotonic() > deadline:
                            self.fail("The preview did not start")
                        time.sleep(0.05)
                    children = [int(pid) for pid in pid_file.read_text().split()]
                    wrapper.send_signal(signum)
                    wrapper.wait(timeout=30)
                    # The orphaned worker is reaped by init once it is killed.
                    deadline = time.monotonic() + 5
                    while any(alive(pid) for pid in children) and time.monotonic() < deadline:
                        time.sleep(0.05)
                    self.assertEqual(
                        [pid for pid in children if alive(pid)], [],
                        "Ansible processes outlived the guard",
                    )
                    self.assertEqual(
                        list(temporary.glob("dotfiles-ansible-home-*")), []
                    )
                    self.assertEqual(wrapper.returncode, status)
                finally:
                    if wrapper.poll() is None:
                        wrapper.kill()
                        wrapper.wait()
                    for pid in children:
                        if alive(pid):
                            os.kill(pid, signal.SIGKILL)

    def preserve_signal_handlers(self):
        previous = {
            signum: signal.getsignal(signum)
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        }
        self.addCleanup(lambda: [signal.signal(*item) for item in previous.items()])

    def test_termination_handling_keeps_ignored_signals_ignored(self):
        self.preserve_signal_handlers()
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        exit_on_termination()
        self.assertIs(signal.getsignal(signal.SIGHUP), signal.SIG_IGN)
        self.assertTrue(callable(signal.getsignal(signal.SIGTERM)))

    def test_termination_while_ansible_starts_still_stops_its_group(self):
        self.preserve_signal_handlers()
        exit_on_termination()
        self.addCleanup(lambda: setattr(safe_run.termination, "pending", None))
        started = []
        real_popen = subprocess.Popen

        def popen_then_terminate(*args, **kwargs):
            # The signal lands after the child exists but before the guard
            # has returned from starting it.
            started.append(real_popen(*args, **kwargs))
            os.kill(os.getpid(), signal.SIGTERM)
            return started[-1]

        command = [sys.executable, "-c", "import time; time.sleep(60)"]
        with patch(
            "scripts.deploy.ansible_safe_run.subprocess.Popen",
            side_effect=popen_then_terminate,
        ):
            with self.assertRaises(SystemExit) as stopped:
                ansible_run(command)
        self.assertEqual(stopped.exception.code, 128 + signal.SIGTERM)
        self.assertIsNotNone(started[0].poll())
        with self.assertRaises(ProcessLookupError):
            os.killpg(started[0].pid, 0)

    def test_fact_gathering_rejects_unneeded_or_executable_collectors(self):
        required = ["!all", "!min", "distribution", "user"]
        for subsets in (
            ["!facter", "!ohai"],
            ["all"],
            ["!all", "distribution", "user"],
            *(required + [extra] for extra in ("hardware", "network", "local", "facter", "ohai")),
        ):
            with self.subTest(subsets=subsets):
                path = self.root / "facts.yaml"
                path.write_text(
                    "- hosts: all\n  gather_facts: false\n  tasks:\n"
                    "    - name: Gather facts\n      ansible.builtin.setup:\n"
                    "        fact_path: /dev/null\n"
                    f"        gather_subset: {json.dumps(subsets)}\n"
                )
                with patch("scripts.deploy.ansible_safe_run.subprocess.run") as run:
                    with self.assertRaisesRegex(UnsafePreview, "Fact gathering"):
                        main([str(path), "--check"])
                    run.assert_not_called()

    def test_repository_fact_gathering_uses_only_required_collectors(self):
        from ansible.module_utils.facts import collector, default_collectors

        for name, system in (("macos", "Darwin"), ("ubuntu-linux", "Linux"), ("arch-linux", "Linux")):
            for tags in ({"all"}, {"files"}):
                with self.subTest(playbook=name, tags=tags):
                    playbook = Path(f"ansible/playbook-{name}.yaml")
                    play = safe_run.yaml.safe_load(playbook.read_text())[0]
                    self.assertIs(play.get("gather_facts"), False)
                    expected, _, _ = audit(playbook, tags, set(), {"clone_dotfiles": False})
                    setups = [task[action] for action, task in expected.values()
                              if action == "ansible.builtin.setup"]
                    self.assertEqual(setups, [{
                        "fact_path": "/dev/null",
                        "gather_subset": ["!all", "!min", "distribution", "user"],
                    }])
                    classes = collector.collector_classes_from_gather_subset(
                        all_collector_classes=default_collectors.collectors,
                        gather_subset=setups[0]["gather_subset"],
                        # !all alone retains local facts; !min is required.
                        minimal_gather_subset={"local"},
                        platform_info={"system": system},
                    )
                    self.assertEqual(
                        {item.name for item in classes}, {"distribution", "user"}
                    )

    def test_repository_playbooks_are_audited(self):
        for name in ("macos", "ubuntu-linux", "arch-linux"):
            for tags in ({"all"}, {"files"}):
                with self.subTest(playbook=name, tags=tags):
                    expected, _, _ = audit(
                        Path(f"ansible/playbook-{name}.yaml"),
                        tags, set(), {"clone_dotfiles": False},
                    )
                    self.assertGreater(len(expected), 5)

    def test_arch_default_separates_files_from_legacy_system_tasks(self):
        play = safe_run.yaml.safe_load(Path("ansible/playbook-arch-linux.yaml").read_text())[0]
        self.assertEqual(play["connection"], "local")
        self.assertIs(play["become"], False)
        self.assertEqual(play["pre_tasks"][1]["when"], "ansible_facts['os_family'] not in ['Archlinux']")
        self.assertEqual(play["pre_tasks"][1]["tags"], ["always"])
        self.assertIn("ansible.builtin.fail", play["pre_tasks"][1])
        files = [
            "tasks/clone-dotfiles-into-home.yaml", "tasks/files.yaml",
            "tasks/arch-linux/files.yaml", "tasks/mcabber.yaml", "tasks/weechat.yaml",
        ]
        self.assertEqual([task["ansible.builtin.import_tasks"] for task in play["tasks"]], files)
        legacy = Path("ansible/playbook-arch-linux-system.yaml")
        self.assertTrue(legacy.is_file(), "Keep the original mixed system playbook")
        system = safe_run.yaml.safe_load(legacy.read_text())[0]
        privileged = [
            "tasks/arch-linux/reflector.yaml", "tasks/arch-linux/install-xorg-packages.yaml",
            "tasks/arch-linux/install-console-packages.yaml", "tasks/arch-linux/users.yaml",
        ]
        self.assertEqual(
            [task["ansible.builtin.import_tasks"] for task in system["tasks"]],
            privileged[:3] + files[:3] + privileged[3:] + files[3:],
        )
        self.assertEqual(
            [task["ansible.builtin.import_tasks"] for task in system["tasks"] if task.get("become")],
            privileged,
        )
        vagrant = Path("Vagrantfile").read_text()
        self.assertIn('ansible.playbook = "ansible/playbook-arch-linux-system.yaml"', vagrant)
        self.assertNotIn('ansible.playbook = "ansible/playbook-arch-linux.yaml"', vagrant)

    def test_arch_files_use_safe_home_relative_mappings(self):
        tasks = safe_run.yaml.safe_load(Path("ansible/tasks/arch-linux/files.yaml").read_text())
        home = "{{ dotfiles_home | default(ansible_facts['user_dir']) }}/"
        source = "{{ dotfiles_dir }}/files/"
        links, directories = [], []
        for task in tasks:
            with self.subTest(task=task["name"]):
                spec = task["ansible.builtin.file"]
                destination = spec.get("dest", spec.get("path"))
                self.assertTrue(destination.startswith(home), destination)
                if spec["state"] == "link":
                    self.assertIs(spec.get("force"), False)
                    self.assertIs(spec.get("follow"), False)
                    self.assertTrue(spec["src"].startswith(source))
                for item in task.get("loop", [{}]):
                    self.assertNotIn("{{", str(item))
                    relative = destination.removeprefix(home)
                    if isinstance(item, dict):
                        relative = relative.replace("{{ item.dest }}", item.get("dest", ""))
                    else:
                        relative = relative.replace("{{ item }}", item)
                    self.assertFalse(relative.startswith(("/", "~")))
                    self.assertNotIn("..", Path(relative).parts)
                    self.assertNotIn("{{", relative)
                    if spec["state"] == "link":
                        src = spec["src"].removeprefix(source).replace("{{ item.src }}", item.get("src", ""))
                        self.assertTrue((Path("files") / src).exists(), src)
                        links.append((src, relative))
                    else:
                        directories.append(relative.rstrip("/"))
        self.assertCountEqual(links, [
            ("visual-studio-code-settings.json", ".config/Code - OSS/User/settings.json"),
            ("visual-studio-code-keybindings.json", ".config/Code - OSS/User/keybindings.json"),
            ("visual-studio-code-settings.json", ".config/Code/User/settings.json"),
            ("visual-studio-code-keybindings.json", ".config/Code/User/keybindings.json"),
            ("cursor-settings.json", ".config/Cursor/User/settings.json"),
            ("antigravity-settings.json", ".config/Antigravity/User/settings.json"),
            ("xinitrc", ".xinitrc"), ("Xresources", ".Xresources"),
            ("xmonad.hs", ".xmonad/xmonad.hs"), ("xmobarrc.hs", ".xmobarrc"),
        ])
        self.assertCountEqual(directories, [
            ".config/Code - OSS/User", ".config/Code/User", ".config/Cursor/User",
            ".config/Antigravity/User", ".xmonad",
        ])

    def test_arch_system_and_vm_are_blocked_before_subprocess(self):
        for name in ("arch-linux-system", "arch-linux-vm"):
            for tags in ([], ["--tags", "files"], ["--skip-tags", "all,always"]):
                for mode in ([], ["--check"]):
                    with self.subTest(playbook=name, tags=tags, mode=mode), patch(
                        "scripts.deploy.ansible_safe_run.subprocess.run",
                    ) as run:
                        with self.assertRaises(UnsafePreview):
                            main([f"ansible/playbook-{name}.yaml", *mode, *tags])
                        run.assert_not_called()

    def test_unselected_imports_cannot_hide_unsafe_modules(self):
        path, _ = self.safe_directory_plan()
        play = safe_run.yaml.safe_load(path.read_text())
        play[0]["tasks"][0]["tags"] = ["files"]
        play[0]["tasks"].append({
            "name": "Unselected system tasks", "tags": ["system"],
            "ansible.builtin.import_tasks": "unsafe-import.yaml",
        })
        path.write_text(safe_run.yaml.safe_dump(play))
        for action, arguments in (
            ("community.general.pacman", {"name": "example", "state": "present"}),
            ("ansible.builtin.user", {"name": "example"}),
            ("ansible.builtin.reboot", {}),
            ("ansible.builtin.command", "touch /should-not-exist"),
        ):
            (self.root / "unsafe-import.yaml").write_text(safe_run.yaml.safe_dump([
                {"name": "Unsafe imported task", action: arguments},
            ]))
            for tags in (["--tags", "files"], ["--skip-tags", "system"], ["--skip-tags", "all,always"]):
                with self.subTest(action=action, tags=tags), patch(
                    "scripts.deploy.ansible_safe_run.subprocess.run",
                ) as run:
                    with self.assertRaisesRegex(UnsafePreview, "No safe preview|Opaque commands"):
                        main([str(path), "--check", *tags])
                    run.assert_not_called()

    def host_release(self):
        if sys.platform.startswith("linux"):
            try:
                return platform.freedesktop_os_release()
            except OSError:
                pass
        return {}

    def launcher_checkout(self):
        if sys.prefix == sys.base_prefix:
            self.skipTest("Real launcher preview requires installed venv dependencies")
        repo = Path(__file__).resolve().parents[1]
        checkout = self.root / "checkout with spaces"
        checkout.mkdir()
        for name in ("ansible", "files"):
            shutil.copytree(repo / name, checkout / name)
        shutil.copy2(repo / "runAnsible.sh", checkout)
        guard = checkout / "scripts/deploy/ansible_safe_run.py"
        guard.parent.mkdir(parents=True)
        shutil.copy2(repo / "scripts/deploy/ansible_safe_run.py", guard)
        # Reuse installed dependencies without a network install in this test.
        (checkout / ".venv").symlink_to(sys.prefix, target_is_directory=True)
        (checkout / "requirements.txt").write_text("")
        return checkout

    def launcher_preview(self, checkout, home):
        return subprocess.run(
            [str(checkout / "runAnsible.sh"), "--check", "--diff", "--tags", "files",
             "-e", json.dumps({"dotfiles_home": str(home)})],
            cwd=self.root, capture_output=True, text=True, check=False, timeout=90,
        )

    def test_launcher_previews_checkout_with_spaces_from_another_directory(self):
        release = self.host_release()
        if not (
            sys.platform == "darwin"
            or release.get("ID") == "arch"
            or (release.get("ID") == "ubuntu" and release.get("VERSION_ID") == "24.04")
            or (release.get("ID") == "linuxmint" and release.get("VERSION_ID", "").split(".")[0] == "22")
        ):
            self.skipTest("Real launcher preview requires macOS, Arch Linux, Ubuntu 24.04, or Mint 22")
        checkout = self.launcher_checkout()
        home = self.root / "new home"
        result = self.launcher_preview(checkout, home)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Safe preview:", result.stdout)
        self.assertIn(f"Would create link: {home / '.bashrc'}", result.stdout)
        if release.get("ID") == "arch":
            for name in (".xinitrc", ".config/Code - OSS/User/settings.json", ".config/Cursor/User/settings.json"):
                self.assertIn(f"Would create link: {home / name}", result.stdout)
        self.assertFalse(home.exists())

    def test_arch_launcher_preserves_conflicting_files_and_symlinks(self):
        if self.host_release().get("ID") != "arch":
            self.skipTest("Arch launcher conflicts require actual Arch Linux")
        checkout = self.launcher_checkout()
        for name in (".xinitrc", ".config/Code - OSS/User/settings.json"):
            for kind in ("file", "link"):
                with self.subTest(destination=name, kind=kind), tempfile.TemporaryDirectory(dir=self.root) as directory:
                    home = Path(directory)
                    target = home / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    other = home / "irreplaceable-source"
                    other.write_text("keep this configuration\n")
                    if kind == "file":
                        target.write_text("keep this existing file\n")
                    else:
                        target.symlink_to(other)
                    before = {entry.relative_to(home): fingerprint(entry) for entry in home.rglob("*")}
                    result = self.launcher_preview(checkout, home)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("Apply blocked:", result.stderr)
                    self.assertNotIn("Applying the same", result.stdout)
                    self.assertEqual(
                        {entry.relative_to(home): fingerprint(entry) for entry in home.rglob("*")}, before,
                    )


if __name__ == "__main__":
    unittest.main()

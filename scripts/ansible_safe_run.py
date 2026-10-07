"""Preview the repository's local playbooks before any configuration changes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import yaml


class UnsafePreview(ValueError):
    """The selected tasks cannot establish a non-destructive apply."""


READ_ONLY = {"ansible.builtin.stat", "ansible.builtin.find", "ansible.builtin.fail"}
RESTARTS = {"/usr/bin/killall Finder", "/usr/bin/killall SystemUIServer"}
TASK_KEYS = {
    "name",
    "args",
    "register",
    "when",
    "loop",
    "notify",
    "tags",
    "become",
    "changed_when",
    "failed_when",
    "check_mode",
}


def selected(tags, include, exclude):
    tags = set(tags)
    return not tags.intersection(exclude) and (
        "always" in tags
        or ("never" not in tags and "all" in include)
        or bool(tags.intersection(include))
        or ("tagged" in include and bool(tags))
        or ("untagged" in include and not tags)
    )


def audit(playbook, include, exclude):
    """Audit even unselected tasks before invoking check mode; imports are static."""
    expected, handlers, files = {}, {}, set()

    def tasks(path, data, nodes, inherited=(), handler=False):
        for task, node in zip(data, nodes.value, strict=True):
            if not isinstance(task, dict):
                raise UnsafePreview("Tasks must use explicit module mappings")
            actions = [key for key in task if key not in TASK_KEYS]
            if len(actions) != 1 or task.get("check_mode", True) is not True:
                raise UnsafePreview("Unknown task controls or check_mode override")
            if "ansible_check_mode" in str(task.get("when", "")):
                raise UnsafePreview("Check-mode conditions cannot hide apply effects")
            if "loop" in task and not isinstance(task["loop"], list):
                raise UnsafePreview(
                    "Dynamic loops cannot establish complete item previews"
                )
            action = actions[0]
            value = task[action]
            tags = set(inherited) | set(task.get("tags", []))
            if action == "ansible.builtin.import_tasks":
                if not isinstance(value, str) or "{{" in value:
                    raise UnsafePreview("Dynamic imports cannot establish completeness")
                child = (path.parent / value).resolve()
                child_data, child_node = load(child)
                tasks(child, child_data, child_node, tags, handler)
                continue
            if action in READ_ONLY:
                pass
            elif action == "ansible.builtin.file":
                if not isinstance(value, dict) or value.get("state") not in {
                    "directory",
                    "link",
                }:
                    raise UnsafePreview(
                        "Only directory and symlink file tasks are audited"
                    )
                if (
                    task.get("changed_when") is not None
                    or task.get("failed_when") is not None
                ):
                    raise UnsafePreview("File tasks cannot hide changes or failures")
            elif action == "ansible.builtin.git":
                if value.get("force") is not False or value.get("update") is not False:
                    raise UnsafePreview(
                        "Git check mode must not force or fetch updates"
                    )
            elif action == "community.general.osx_defaults":
                if (
                    value.get("state", "present") != "present"
                    or value.get("type") != "bool"
                ):
                    raise UnsafePreview(
                        "Only in-place boolean macOS preferences are audited"
                    )
            elif action == "ansible.builtin.command":
                if (
                    not handler
                    or value not in RESTARTS
                    or task.get("changed_when") is not False
                ):
                    raise UnsafePreview(
                        "Opaque commands need a proven read-only preview"
                    )
            else:
                raise UnsafePreview(f"No safe preview is established for {action}")
            ref = f"{path}:{node.start_mark.line + 1}"
            record = (action, task)
            if handler:
                handlers[ref] = record
            elif selected(tags, include, exclude):
                expected[ref] = record

    def load(path):
        if not path.is_relative_to(playbook.parent.resolve()):
            raise UnsafePreview("Imports must remain inside the Ansible directory")
        files.add(path)
        text = path.read_text()
        return yaml.safe_load(text), yaml.compose(text)

    playbook = playbook.resolve()
    data, nodes = load(playbook)
    for play, play_node in zip(data, nodes.value, strict=True):
        if any(
            key in play
            for key in (
                "roles",
                "vars_files",
                "module_defaults",
                "environment",
                "strategy",
            )
        ):
            raise UnsafePreview("Unaudited playbook execution controls")
        if play.get("check_mode", True) is not True:
            raise UnsafePreview("Playbook check_mode override")
        node_map = {key.value: value for key, value in play_node.value}
        for section in ("pre_tasks", "tasks", "post_tasks", "handlers"):
            if section in play:
                tasks(
                    playbook,
                    play[section],
                    node_map[section],
                    play.get("tags", []),
                    section == "handlers",
                )
    if not expected:
        raise UnsafePreview("No selected tasks")
    return expected, handlers, files


def fingerprint(path):
    """Bind targets and source files to the state observed after the preview."""
    path = Path(path)
    if path.is_symlink():
        return ("link", os.readlink(path))
    if not path.exists():
        return ("absent",)
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return (stat.st_mode, stat.st_uid, stat.st_gid, stat.st_mtime_ns, digest)


def inspect_preview(plan, expected, handlers):
    if (
        not isinstance(plan, dict)
        or not plan.get("plays")
        or set(plan.get("stats", {})) != {"127.0.0.1"}
    ):
        raise UnsafePreview("Missing play or localhost recap")
    stats = plan["stats"]["127.0.0.1"]
    if any(
        stats.get(key) != 0 for key in ("failures", "unreachable", "ignored", "rescued")
    ):
        raise UnsafePreview("Preview contains failed, unreachable, or hidden results")
    observed, snapshots, restarts, directories = set(), {}, set(), set()
    for play in plan["plays"]:
        for entry in play.get("tasks", []):
            filename, separator, line = entry["task"]["path"].rpartition(":")
            if not separator or not line.isdecimal():
                raise UnsafePreview("Preview task has no source location")
            ref = f"{Path(filename).resolve()}:{line}"
            record = expected.get(ref) or handlers.get(ref)
            hosts = entry.get("hosts", {})
            if set(hosts) != {"127.0.0.1"}:
                raise UnsafePreview("Missing task result or unexpected host")
            result = hosts["127.0.0.1"]
            if record is None:
                if result.get("action") in {
                    "ansible.builtin.gather_facts",
                    "gather_facts",
                }:
                    continue
                raise UnsafePreview("A task ran outside the audited selection")
            action, task = record
            if result.get("action") != action:
                raise UnsafePreview("Preview action differs from the audited task")
            observed.add(ref)
            if action == "ansible.builtin.command":
                if (
                    not result.get("skipped")
                    or result.get("msg")
                    != "Command would have run if not in check mode"
                    or result.get("cmd") != shlex.split(task[action])
                ):
                    raise UnsafePreview(
                        "Restart handler did not remain read-only in check mode"
                    )
                restarts.add(task[action].split()[1])
                continue
            items = result.get("results", [result])
            if not items:
                raise UnsafePreview("Empty loop preview")
            if "loop" in task and len(items) != len(task["loop"]):
                raise UnsafePreview("Incomplete loop preview")
            for item in items:
                if (
                    item.get("failed")
                    or item.get("unreachable")
                    or "changed" not in item
                ):
                    raise UnsafePreview("Failed or incomplete item preview")
                if item.get("skipped"):
                    if (
                        item.get("skip_reason") != "Conditional result was False"
                        or "false_condition" not in item
                    ):
                        raise UnsafePreview("A task has no proven conditional skip")
                    continue
                if action == "ansible.builtin.git" and item["changed"]:
                    raise UnsafePreview(
                        "Clone effects require a materialized source before the complete preview"
                    )
                if action != "ansible.builtin.file":
                    continue
                diff = item.get("diff", {})
                before, after = diff.get("before", {}), diff.get("after", {})
                path = after.get("path")
                if not path or before.get("path") != path:
                    raise UnsafePreview(
                        "File preview has no complete before/after path"
                    )
                state = task[action]["state"]
                previous = before.get("state", state)
                if (
                    previous not in {"absent", state}
                    or after.get("state", state) != state
                ):
                    raise UnsafePreview(
                        "Preview would replace or remove an existing path"
                    )
                if state == "link":
                    if "src" in before or "src" in after:
                        raise UnsafePreview(
                            "Preview would replace an existing symlink target"
                        )
                    source = item.get("src")
                    if not source or not Path(source).exists():
                        raise UnsafePreview(
                            "Symlink source does not exist during the preview"
                        )
                    snapshots[source] = fingerprint(source)
                    parent = Path(path).parent
                    if not parent.is_dir() and parent not in directories:
                        raise UnsafePreview(
                            "Symlink parent directory is neither present nor planned"
                        )
                    snapshots[str(parent)] = fingerprint(parent)
                else:
                    parent = Path(path)
                    directories.update([parent, *parent.parents])
                current = fingerprint(path)
                if previous == "absent" and current != ("absent",):
                    raise UnsafePreview(
                        "A destination appeared after its absent-state preview"
                    )
                if previous == "link" and current[0] != "link":
                    raise UnsafePreview("A symlink changed type after the preview")
                snapshots[path] = current
    if not set(expected).issubset(observed):
        raise UnsafePreview("Selected tasks were omitted from the preview")
    return snapshots, restarts


def preview_restarts(names):
    # macOS killall(1): -s prints matching processes and sends no signal.
    for name in sorted(names):
        if name not in {"Finder", "SystemUIServer"} or sys.platform != "darwin":
            raise UnsafePreview("Unknown restart target or unsupported platform")
        result = subprocess.run(
            ["/usr/bin/killall", "-s", name], capture_output=True, text=True
        )
        if result.returncode not in (0, 1):
            raise UnsafePreview("macOS restart preview failed")
        print(f"Read-only restart preview: {name} (no signals sent)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("playbook", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--tags", default="all")
    parser.add_argument("--skip-tags", default="")
    parser.add_argument("-e", "--extra-vars", action="append", default=[])
    args = parser.parse_args(argv)
    variables = {}
    for value in args.extra_vars:
        if value.startswith("{"):
            variables.update(json.loads(value))
        else:
            for pair in shlex.split(value):
                key, separator, item = pair.partition("=")
                if not separator:
                    raise UnsafePreview(
                        "Use explicit key=value or JSON extra variables"
                    )
                variables[key] = item
    if set(variables) - {
        "dotfiles_dir",
        "dotfiles_home",
        "clone_dotfiles",
        "ansible_python_interpreter",
    }:
        raise UnsafePreview(
            "Extra variables cannot override execution or check-mode controls"
        )
    if any(
        not isinstance(value, (str, bool)) or "{{" in str(value) or "{%" in str(value)
        for value in variables.values()
    ):
        raise UnsafePreview("Extra variables must be literal paths or booleans")
    for key in ("dotfiles_dir", "dotfiles_home", "ansible_python_interpreter"):
        if key in variables and not Path(variables[key]).is_absolute():
            raise UnsafePreview(f"{key} must be an absolute path")
    expected, handlers, files = audit(
        args.playbook, set(args.tags.split(",")), set(args.skip_tags.split(","))
    )
    files.add(Path("ansible/inventory.yaml").resolve())
    files.add(Path("ansible/ansible.cfg").resolve())
    files.add(Path(__file__).resolve())
    config = {str(path): fingerprint(path) for path in files}
    if "dotfiles_dir" in variables:
        config[variables["dotfiles_dir"]] = fingerprint(variables["dotfiles_dir"])
    command = [
        "ansible-playbook",
        "-i",
        "ansible/inventory.yaml",
        str(args.playbook),
        "-l",
        "127.0.0.1",
        "--tags",
        args.tags,
        "--skip-tags",
        args.skip_tags,
    ]
    command.extend(["-e", json.dumps(variables)])
    environment = dict(
        os.environ,
        ANSIBLE_CONFIG=str(Path("ansible/ansible.cfg").resolve()),
        ANSIBLE_COLLECTIONS_PATH=str(Path(".ansible/collections").resolve()),
        ANSIBLE_STDOUT_CALLBACK="ansible.posix.json",
        ANSIBLE_NOCOLOR="1",
    )
    preview = subprocess.run(
        command + ["--check", "--diff"], env=environment, capture_output=True, text=True
    )
    if preview.stderr:
        print(preview.stderr, file=sys.stderr, end="")
    if preview.returncode:
        raise UnsafePreview("Ansible preview failed; apply was not started")
    snapshots, restarts = inspect_preview(
        json.loads(preview.stdout), expected, handlers
    )
    preview_restarts(restarts)
    print(
        f"Safe preview: {len(expected)} selected tasks; no deletions, overwrites, or missing effects"
    )
    if args.check:
        return 0
    for path, previous in {**config, **snapshots}.items():
        if fingerprint(path) != previous:
            raise UnsafePreview(
                "Configuration or target state changed after the preview"
            )
    print(
        "Applying the same playbook, inventory, variables, and selected tasks",
        flush=True,
    )
    environment["ANSIBLE_STDOUT_CALLBACK"] = "default"
    return subprocess.run(
        command + (["--diff"] if args.diff else []), env=environment
    ).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (UnsafePreview, json.JSONDecodeError, KeyError, TypeError, OSError) as error:
        print(f"Apply blocked: {error}", file=sys.stderr)
        sys.exit(1)

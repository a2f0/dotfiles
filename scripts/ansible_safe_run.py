"""Preview the repository's local playbooks before any configuration changes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import sysconfig
import tempfile

try:
    import yaml
except ImportError as error:
    raise SystemExit("PyYAML is required; install requirements.txt in the active Python environment") from error


class UnsafePreview(ValueError):
    """The selected tasks cannot establish a non-destructive apply."""


READ_ONLY = {"ansible.builtin.stat", "ansible.builtin.find", "ansible.builtin.fail"}
RESTARTS = {"/usr/bin/killall Finder", "/usr/bin/killall SystemUIServer"}
TRUSTED_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
TASK_KEYS = {
    "name",
    "register",
    "when",
    "loop",
    "notify",
    "tags",
    "changed_when",
    "failed_when",
    "check_mode",
}
PLAY_KEYS = {
    "name",
    "hosts",
    "connection",
    "become",
    "vars",
    "gather_facts",
    "tags",
    "check_mode",
    "pre_tasks",
    "tasks",
    "post_tasks",
    "handlers",
}
STABLE_EXPRESSIONS = {
    "dotfiles_dir",
    "dotfiles_dir | default('~/dotfiles')",
    "dotfiles_home | default(ansible_facts['user_dir'])",
    "ansible_facts['user_id']",
    "item",
    "item.src",
    "item.dest",
}
CLONE_CONDITION = "clone_dotfiles | default(true) | bool"
STABLE_CONDITIONS = {
    CLONE_CONDITION,
    "ansible_facts['os_family'] != 'Darwin'",
    "not ( (ansible_facts['distribution'] == 'Ubuntu' and ansible_facts['distribution_version'] is version('24.04', '==')) or (ansible_facts['distribution'] == 'Linux Mint' and ansible_facts['distribution_major_version'] is version('22', '==')) )",
    "dotfiles_dir_stat.stat.exists",
    "not dotfiles_dir_stat.stat.isdir",
    "dotfiles_dir_stat.stat.isdir",
    "(not dotfiles_dir_stat.stat.exists) or (dotfiles_dir_entries.matched | int == 0)",
}
RESTART_FAILURES = {
    "/usr/bin/killall Finder": ("kill_finder", "kill_finder.rc > 1"),
    "/usr/bin/killall SystemUIServer": ("kill_systemuiserver", "kill_systemuiserver.rc > 1"),
}
PLUGIN_DIRECTORIES = {
    "ANSIBLE_ACTION_PLUGINS": "action",
    "ANSIBLE_BECOME_PLUGINS": "become",
    "ANSIBLE_CACHE_PLUGINS": "cache",
    "ANSIBLE_CALLBACK_PLUGINS": "callback",
    "ANSIBLE_CLICONF_PLUGINS": "cliconf",
    "ANSIBLE_CONNECTION_PLUGINS": "connection",
    "ANSIBLE_DOC_FRAGMENT_PLUGINS": "doc_fragments",
    "ANSIBLE_FILTER_PLUGINS": "filter",
    "ANSIBLE_HTTPAPI_PLUGINS": "httpapi",
    "ANSIBLE_INVENTORY_PLUGINS": "inventory",
    "ANSIBLE_LOOKUP_PLUGINS": "lookup",
    "ANSIBLE_NETCONF_PLUGINS": "netconf",
    "ANSIBLE_SHELL_PLUGINS": "shell",
    "ANSIBLE_STRATEGY_PLUGINS": "strategy",
    "ANSIBLE_TERMINAL_PLUGINS": "terminal",
    "ANSIBLE_TEST_PLUGINS": "test",
    "ANSIBLE_VARS_PLUGINS": "vars",
}
LOCAL_PLUGIN_DIRECTORIES = {
    "action_plugins", "become_plugins", "cache_plugins", "callback_plugins",
    "cliconf_plugins", "collections", "connection_plugins", "doc_fragments",
    "filter_plugins", "httpapi_plugins", "inventory_plugins", "library",
    "lookup_plugins", "module_utils", "netconf_plugins", "roles",
    "shell_plugins", "strategy_plugins", "terminal_plugins", "test_plugins",
    "vars_plugins",
}


def normalized_tags(tags):
    if isinstance(tags, str):
        tags = [tags]
    if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
        if any("{{" in tag or "{%" in tag for tag in tags):
            raise UnsafePreview("Dynamic tags cannot establish task selection")
        return set(tags)
    raise UnsafePreview("Tags must be a string or list of strings")


def selected(tags, include, exclude):
    tags = set(tags)
    return not tags.intersection(exclude) and (
        "always" in tags
        or ("never" not in tags and "all" in include)
        or bool(tags.intersection(include))
        or ("tagged" in include and bool(tags))
        or ("untagged" in include and not tags)
    )


def audit(playbook, include, exclude, variables=None):
    """Audit even unselected tasks before invoking check mode; imports are static."""
    variables = variables or {}
    expected, handlers, files = {}, {}, set()

    def tasks(path, data, nodes, inherited=(), handler=False):
        for task, node in zip(data, nodes.value, strict=True):
            if not isinstance(task, dict):
                raise UnsafePreview("Tasks must use explicit module mappings")
            actions = [key for key in task if key not in TASK_KEYS]
            if len(actions) != 1 or task.get("check_mode", True) is not True:
                raise UnsafePreview("Unknown task controls or check_mode override")
            if "ansible_check_mode" in str(task):
                raise UnsafePreview("Check-mode-dependent tasks cannot match the apply")
            if "{%" in str(task) or "{#" in str(task):
                raise UnsafePreview("Unaudited Jinja blocks cannot run during a preview")
            for expression in re.findall(r"\{\{(.*?)\}\}", str(task), flags=re.DOTALL):
                if expression.strip() not in STABLE_EXPRESSIONS:
                    raise UnsafePreview("Task template can change between preview and apply")
            if "loop" in task and not isinstance(task["loop"], list):
                raise UnsafePreview(
                    "Dynamic loops cannot establish complete item previews"
                )
            if "loop" in task and "{{" in str(task["loop"]):
                raise UnsafePreview("Loop items must be literal")
            action = actions[0]
            value = task[action]
            restart_failure = (
                RESTART_FAILURES.get(value, (None, None))
                if isinstance(value, str)
                else (None, None)
            )
            if "when" in task:
                conditions = task["when"] if isinstance(task["when"], list) else [task["when"]]
                if not conditions or any(
                    not isinstance(condition, str)
                    or " ".join(condition.split()) not in STABLE_CONDITIONS
                    for condition in conditions
                ):
                    raise UnsafePreview("Unaudited task condition could run during preview")
            if "failed_when" in task and (
                action != "ansible.builtin.command"
                or task.get("register") != restart_failure[0]
                or task["failed_when"] != restart_failure[1]
            ):
                raise UnsafePreview("Unaudited failure condition could run during preview")
            if "changed_when" in task and (
                action != "ansible.builtin.command" or task["changed_when"] is not False
            ):
                raise UnsafePreview("Unaudited change condition could run during preview")
            if "notify" in task and (
                action != "community.general.osx_defaults"
                or not isinstance(task["notify"], list)
                or any(
                    not isinstance(name, str)
                    or name not in {"Restart Finder", "Restart SystemUIServer"}
                    for name in task["notify"]
                )
            ):
                raise UnsafePreview("Unaudited handler notification")
            tags = set(inherited) | normalized_tags(task.get("tags", []))
            if action == "ansible.builtin.import_tasks":
                if "when" in task:
                    raise UnsafePreview("Conditional task imports cannot be previewed safely")
                if not isinstance(value, str) or "{{" in value:
                    raise UnsafePreview("Dynamic imports cannot establish completeness")
                child = (path.parent / value).resolve()
                child_data, child_node = load(child)
                tasks(child, child_data, child_node, tags, handler)
                continue
            if action == "ansible.builtin.setup":
                if value != {
                    "fact_path": "/dev/null",
                    "gather_subset": ["!facter", "!ohai"],
                } or "when" in task:
                    raise UnsafePreview("Fact gathering must disable executable local facts")
            elif action in READ_ONLY:
                pass
            elif action == "ansible.builtin.file":
                if "when" in task:
                    raise UnsafePreview("Conditional file changes cannot be previewed safely")
                if not isinstance(value, dict) or value.get("state") not in {
                    "directory",
                    "link",
                }:
                    raise UnsafePreview(
                        "Only directory and symlink file tasks are audited"
                    )
                if value.get("recurse", False) is not False:
                    raise UnsafePreview("Recursive file changes cannot be previewed completely")
                if (
                    task.get("changed_when") is not None
                    or task.get("failed_when") is not None
                ):
                    raise UnsafePreview("File tasks cannot hide changes or failures")
            elif action == "ansible.builtin.git":
                if (
                    variables.get("clone_dotfiles") not in (False, "false")
                    or not isinstance(task.get("when"), list)
                    or not task["when"]
                    or task["when"][0] != CLONE_CONDITION
                ):
                    raise UnsafePreview("Conditional clone needs an explicit fixed skip")
                if (
                    not isinstance(value, dict)
                    or value.get("force") is not False
                    or value.get("update") is not False
                ):
                    raise UnsafePreview(
                        "Git check mode must not force or fetch updates"
                    )
            elif action == "community.general.osx_defaults":
                if "when" in task:
                    raise UnsafePreview("Conditional preference changes cannot be previewed safely")
                if (
                    not isinstance(value, dict)
                    or set(value) - {"domain", "key", "type", "value", "state"}
                    or value.get("state", "present") != "present"
                    or value.get("type") != "bool"
                    or not isinstance(value.get("domain"), str)
                    or not isinstance(value.get("key"), str)
                    or not isinstance(value.get("value"), bool)
                    or "{{" in value["domain"]
                    or "{{" in value["key"]
                ):
                    raise UnsafePreview(
                        "Only in-place boolean macOS preferences are audited"
                    )
            elif action == "ansible.builtin.command":
                if (
                    not handler
                    or "when" in task
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
        if not isinstance(play, dict) or set(play) - PLAY_KEYS:
            raise UnsafePreview("Unaudited playbook execution controls")
        if "name" in play and (
            not isinstance(play["name"], str)
            or any(token in play["name"] for token in ("{{", "{%", "{#"))
        ):
            raise UnsafePreview("Play names cannot evaluate templates during preview")
        if play.get("hosts") not in ("all", "127.0.0.1") or play.get("gather_facts", True) not in (True, False):
            raise UnsafePreview("Playbook host or fact selection is not fixed")
        if play.get("connection", "local") != "local" or play.get("become", False) is not False:
            raise UnsafePreview("Playbooks must use local execution without privilege escalation")
        if not isinstance(play.get("vars", {}), dict) or set(play.get("vars", {})) - {
            "dotfiles_dir",
            "ansible_python_interpreter",
        }:
            raise UnsafePreview("Unaudited playbook variables")
        if "ansible_check_mode" in str(play.get("vars", {})):
            raise UnsafePreview("Check-mode-dependent play variables")
        play_vars = play.get("vars", {})
        if (
            "dotfiles_dir" in play_vars
            and play_vars["dotfiles_dir"] not in (
                "{{ playbook_dir | dirname }}",
                "~/dotfiles",
            )
        ) or (
            "ansible_python_interpreter" in play_vars
            and play_vars["ansible_python_interpreter"] != "/usr/bin/python3"
        ):
            raise UnsafePreview("Playbook source and interpreter must remain fixed")
        if play.get("check_mode", True) is not True:
            raise UnsafePreview("Playbook check_mode override")
        node_map = {key.value: value for key, value in play_node.value}
        for section in ("pre_tasks", "tasks", "post_tasks", "handlers"):
            if section in play:
                tasks(
                    playbook,
                    play[section],
                    node_map[section],
                    normalized_tags(play.get("tags", [])),
                    section == "handlers",
                )
        if play.get("gather_facts") is not False:
            raise UnsafePreview("Implicit fact gathering can execute local scripts")
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
    if path.is_dir():
        # Directory contents may change without changing the destination entry.
        return ("directory", stat.st_dev, stat.st_ino, stat.st_mode, stat.st_uid, stat.st_gid)
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return (stat.st_mode, stat.st_uid, stat.st_gid, stat.st_mtime_ns, digest)


def normalized_link_target(path, target):
    return os.path.normpath(os.path.join(os.path.dirname(path), target))


def trusted_runtime():
    """Use only audited configuration and this Python's installed Ansible."""
    config = Path("ansible/ansible.cfg").resolve()
    inventory = Path("ansible/inventory.yaml").resolve()
    if config.read_text().strip() != "[defaults]\ndeprecation_warnings = True":
        raise UnsafePreview("Ansible configuration contains unaudited settings")
    if yaml.safe_load(inventory.read_text()) != {
        "localhost": {"hosts": {"127.0.0.1": {"ansible_connection": "local"}}}
    }:
        raise UnsafePreview("Ansible inventory contains unaudited settings")
    scripts = Path(sysconfig.get_path("scripts")).resolve()
    executable = scripts / "ansible-playbook"
    packages = Path(sysconfig.get_path("purelib")).resolve()
    implementations = [
        executable,
        packages / "ansible/plugins/callback/default.py",
        packages / "ansible_collections/ansible/posix/plugins/callback/json.py",
        packages / "ansible_collections/community/general/plugins/modules/osx_defaults.py",
    ]
    if not all(
        path.is_file()
        and path.resolve().is_relative_to(scripts if path == executable else packages)
        for path in implementations
    ):
        raise UnsafePreview("Required Ansible implementation is outside the installed environment")
    plugin_paths = {
        name: packages / "ansible/plugins" / directory
        for name, directory in PLUGIN_DIRECTORIES.items()
    }
    plugin_paths["ANSIBLE_LIBRARY"] = packages / "ansible/modules"
    if not all(path.is_dir() and path.resolve().is_relative_to(packages) for path in plugin_paths.values()):
        raise UnsafePreview("Ansible plugin paths are outside the installed environment")
    return executable, packages, {config, inventory, *implementations}, plugin_paths


def preference_snapshot(expected):
    """Read selected macOS boolean preferences without writing them."""
    preferences = set()
    for action, task in expected.values():
        if action == "community.general.osx_defaults":
            value = task[action]
            preferences.add((value["domain"], value["key"]))
    snapshot = {}
    for domain, key in sorted(preferences):
        result = subprocess.run(
            ["/usr/bin/defaults", "read", domain, key],
            capture_output=True,
            text=True,
        )
        if result.returncode not in (0, 1):
            raise UnsafePreview("Cannot read macOS preference state")
        snapshot[(domain, key)] = (result.returncode, result.stdout.strip())
    return snapshot


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
    observed, snapshots, restarts, directories, planned = set(), {}, set(), set(), {}
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
                if not isinstance(path, str) or not path or before.get("path") != path:
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
                target = (
                    normalized_link_target(path, item["src"])
                    if state == "link" and isinstance(item.get("src"), str)
                    else None
                )
                proposed = (state, target)
                normalized = os.path.normpath(path)
                destination = os.path.join(
                    os.path.realpath(os.path.dirname(normalized)),
                    os.path.basename(normalized),
                )
                if any(
                    (earlier[0] == "link" and destination.startswith(path + os.sep))
                    or (state == "link" and path.startswith(destination + os.sep))
                    for path, earlier in planned.items()
                ):
                    raise UnsafePreview("Planned symlink cannot be a task ancestor")
                if destination in planned and planned[destination] != proposed:
                    raise UnsafePreview("Conflicting planned file states would replace a path")
                planned[destination] = proposed
                current = fingerprint(path)
                for ancestor in Path(path).parents:
                    snapshots.setdefault(str(ancestor), fingerprint(ancestor))
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
                    if (
                        previous == "link"
                        and current[0] == "link"
                        and normalized_link_target(path, current[1])
                        != normalized_link_target(path, source)
                    ):
                        raise UnsafePreview("Symlink target changed during preview")
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
                if previous == "absent" and current != ("absent",):
                    raise UnsafePreview(
                        "A destination appeared after its absent-state preview"
                    )
                if previous == "link" and current[0] != "link":
                    raise UnsafePreview("A symlink changed type after the preview")
                if previous == "directory" and current[0] != "directory":
                    raise UnsafePreview("A directory changed type after the preview")
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


def describe_changes(plan, expected, handlers):
    """Show reviewed targets without exposing Ansible diff values or file contents."""
    for play in plan["plays"]:
        for entry in play.get("tasks", []):
            filename, _, line = entry["task"]["path"].rpartition(":")
            ref = f"{Path(filename).resolve()}:{line}"
            record = expected.get(ref) or handlers.get(ref)
            if record is None:
                continue
            action, task = record
            result = entry["hosts"]["127.0.0.1"]
            for item in result.get("results", [result]):
                if item.get("skipped") or not item.get("changed"):
                    continue
                if action == "ansible.builtin.file":
                    print(f"Would create {task[action]['state']}: {item['diff']['after']['path']}")
                elif action == "community.general.osx_defaults":
                    print(f"Would update preference: {task[action]['domain']}/{task[action]['key']}")


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
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise UnsafePreview("JSON extra variables must be an object")
            variables.update(parsed)
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
    if (
        "ansible_python_interpreter" in variables
        and (
            Path(variables["ansible_python_interpreter"]).parent
            != Path(sys.executable).parent
            or Path(variables["ansible_python_interpreter"]).resolve()
            != Path(sys.executable).resolve()
        )
    ):
        raise UnsafePreview("Ansible target Python must be the active Python environment")
    for root in {args.playbook.resolve().parent, Path("ansible/inventory.yaml").resolve().parent, Path.cwd()}:
        for name in LOCAL_PLUGIN_DIRECTORIES:
            plugin = root / name
            if plugin.exists() or plugin.is_symlink():
                raise UnsafePreview("Playbook-local plugins and collections are not audited")
    expected, handlers, files = audit(
        args.playbook, set(args.tags.split(",")), set(args.skip_tags.split(",")), variables
    )
    executable, packages, runtime_files, plugin_paths = trusted_runtime()
    files.update(runtime_files)
    files.add(Path(__file__).resolve())
    config = {str(path): fingerprint(path) for path in files}
    source_dir = Path(variables.get("dotfiles_dir", Path.cwd())).resolve()
    config[str(source_dir)] = fingerprint(source_dir)
    command = [
        str(executable),
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
    # Keep the audited module and collection graph independent of user config.
    with tempfile.TemporaryDirectory(prefix="dotfiles-ansible-home-") as isolated_ansible_home:
        environment = dict(
            ((key, value) for key, value in os.environ.items()
             if not key.startswith(("ANSIBLE_", "PYTHON"))),
            ANSIBLE_CONFIG=str(Path("ansible/ansible.cfg").resolve()),
            ANSIBLE_HOME=isolated_ansible_home,
            ANSIBLE_COLLECTIONS_PATH=str(packages),
            ANSIBLE_COLLECTIONS_SCAN_SYS_PATH="False",
            ANSIBLE_VARS_ENABLED="",
            ANSIBLE_STDOUT_CALLBACK="ansible.posix.json",
            ANSIBLE_NOCOLOR="1",
            PATH=TRUSTED_PATH,
            **{name: str(path) for name, path in plugin_paths.items()},
        )
        preferences = preference_snapshot(expected)
        preview = subprocess.run(
            command + ["--check", "--diff"], env=environment, capture_output=True, text=True
        )
        if preview.stderr:
            print(preview.stderr, file=sys.stderr, end="")
        if preview.returncode:
            raise UnsafePreview("Ansible preview failed; apply was not started")
        plan = json.loads(preview.stdout)
        snapshots, restarts = inspect_preview(plan, expected, handlers)
        if preference_snapshot(expected) != preferences:
            raise UnsafePreview("macOS preference state changed during preview")
        preview_restarts(restarts)
        if args.diff:
            describe_changes(plan, expected, handlers)
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
        if preference_snapshot(expected) != preferences:
            raise UnsafePreview("macOS preference state changed after preview")
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
    except (UnsafePreview, json.JSONDecodeError, yaml.YAMLError, KeyError, TypeError, OSError) as error:
        print(f"Apply blocked: {error}", file=sys.stderr)
        sys.exit(1)

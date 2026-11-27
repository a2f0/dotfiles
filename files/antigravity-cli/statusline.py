#!/usr/bin/env python3
"""Antigravity CLI (`agy`) status line: the machine's short hostname, the
working folder, its Git branch, the active model and effort level, the
signed-in email, context window usage, and active quota utilization.

Antigravity CLI pipes session JSON to stdin and shows what this prints.
Mirrors the Claude Code status line and OMP's default `path` segment: a linked
Git worktree shows its project name, temporary directories show their
scratch-relative path, `~/Projects`, `~/repos`, and `/work` prefixes are
dropped, the home directory becomes `~`, and paths longer than 40 characters
keep their end. The folder is a file link.
"""

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

MAX_LENGTH = 40
GIT_SECONDS = 2
FOLDER, SCRATCH, WORKTREE, BRANCH, CONFIG, MODEL, HOST = "📁", "🗑", "🌳", "🌿", "⚙", "🤖", "💻"


def relative_within(root, path):
    """Return `path` relative to `root` ("" when equal), or None outside it."""
    relative = os.path.relpath(path, root)
    if relative == os.curdir:
        return ""
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return None
    return relative


def scratch_roots(home):
    roots = [tempfile.gettempdir(), os.path.join(home, "tmp"), "/tmp", "/var/tmp"]
    return [os.path.realpath(root) for root in roots]


def abbreviate_home(path, home):
    home = home.rstrip("/")
    if home and (path == home or path.startswith(home + "/")):
        return "~" + path[len(home):]
    return path


def clamp(text):
    if len(text) <= MAX_LENGTH:
        return text
    return "…" + text[-(MAX_LENGTH - 1):]


def git(cwd, deadline, *args):
    """Return a Git query's output lines in `cwd`, or None when it fails or the deadline passes."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=remaining,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.splitlines() if result.returncode == 0 else None


def checked_out(cwd, deadline):
    """Name the branch, even before its first commit, or `(commit)` when detached."""
    branch = git(cwd, deadline, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch:
        return branch[0]
    commit = git(cwd, deadline, "rev-parse", "--short", "HEAD")
    return f"({commit[0]})" if commit else None


def worktree_label(git_dir, common_dir, root, branch):
    """Name a linked worktree by its project, adding the directory when it is not the branch."""
    if git_dir == common_dir:
        return None
    # A bare repository's worktrees share `name.git` itself as the project.
    primary = os.path.dirname(common_dir) if os.path.basename(common_dir) == ".git" else common_dir
    project = os.path.basename(primary)
    if project.endswith(".git"):
        project = project[:-len(".git")]
    if not project:
        return None
    directory = os.path.basename(root)
    return project if branch == directory else f"{project}/{directory}"


def git_labels(cwd):
    """Return the folder's worktree label and checked-out branch, each None when absent.

    The queries share one deadline, so a slow repository delays a redraw once.
    """
    deadline = time.monotonic() + GIT_SECONDS
    layout = git(
        cwd, deadline, "rev-parse", "--absolute-git-dir", "--path-format=absolute",
        "--git-common-dir", "--show-toplevel",
    )
    if not layout or len(layout) != 3:
        return None, None
    branch = checked_out(cwd, deadline)
    return worktree_label(*layout, branch), branch


def display_path(cwd, home, scratch):
    """Classify `cwd` as OMP does: scratch-relative, project-relative, or as given."""
    real = os.path.realpath(cwd)
    for root in scratch:
        relative = relative_within(root, real)
        if relative is not None:
            return SCRATCH, relative or cwd
    for root in (os.path.join(home, "Projects"), os.path.join(home, "repos"), "/work"):
        relative = relative_within(os.path.realpath(root), real)
        if relative:
            return FOLDER, relative
    return FOLDER, cwd


def printable(text):
    """Keep control characters, such as terminal escapes, out of the output."""
    return "".join(char if char.isprintable() else "?" for char in text)


def folder(cwd, home, scratch, worktree=None):
    if worktree:
        icon, text = WORKTREE, worktree
    else:
        icon, text = display_path(cwd, home, scratch)
        text = abbreviate_home(text, home)
    text = printable(clamp(text))
    return f"{icon} \x1b]8;;{Path(os.path.abspath(cwd)).as_uri()}\x07{text}\x1b]8;;\x07"


def branch_label(branch):
    return f"{BRANCH} {printable(clamp(branch))}" if branch else None


def host_label(hostname):
    """Name the machine by its hostname up to the first dot, as a shell's `\\h` does."""
    name = hostname.partition(".")[0]
    return f"{HOST} {printable(clamp(name))}" if name else None


def text_field(data, section, key):
    """Return a non-empty string at `data[section][key]`, or None."""
    value = data.get(section)
    value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, str) and value else None


def model_label(data):
    """Name the session's model and effort level when not already in the model name."""
    model = text_field(data, "model", "display_name") or text_field(data, "model", "id")
    if not model:
        return None
    effort = text_field(data, "model", "effort") or text_field(data, "effort", "level")
    if effort and not model.casefold().endswith(f"({effort.casefold()})"):
        names = [model, effort]
    else:
        names = [model]
    return f"{MODEL} " + " · ".join(printable(clamp(name)) for name in names)


def identity_label(data):
    """Name the signed-in account email reported by Antigravity CLI."""
    email = data.get("email")
    if not isinstance(email, str) or not email:
        return None
    return f"{CONFIG} {printable(clamp(email))}"


def percentage(value):
    if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100:
        return f"{value:.0f}%"
    return None


def context_label(data):
    """Show context window usage once the session has a known window and response."""
    window = data.get("context_window")
    if not isinstance(window, dict):
        return None
    if not isinstance(window.get("current_usage"), dict):
        return None
    size = window.get("context_window_size")
    if type(size) not in (int, float) or not math.isfinite(size) or size <= 0:
        return None
    used = percentage(window.get("used_percentage"))
    return f"ctx {used}" if used else None


def parse_iso_timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        # Python 3.9 accepts only three or six fractional-second digits.
        stamp = re.sub(r"\.(\d+)", lambda m: "." + m[1][:6].ljust(6, "0"), value)
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def quota_label(data, now):
    """Show active quota buckets with a remaining fraction as percentage used."""
    quota = data.get("quota")
    if not isinstance(quota, dict):
        return None
    rows = []
    for bucket, entry in sorted(quota.items()):
        if not isinstance(bucket, str) or not bucket or not isinstance(entry, dict):
            continue
        if entry.get("disabled") is True:
            continue
        remaining = entry.get("remaining_fraction")
        if type(remaining) not in (int, float) or not math.isfinite(remaining) or not 0 <= remaining <= 1:
            continue
        reset_time = entry.get("reset_time")
        if reset_time not in (None, ""):
            reset = parse_iso_timestamp(reset_time)
            if reset is None or not reset > now:
                continue
        elif "reset_in_seconds" in entry and entry["reset_in_seconds"] is not None:
            seconds = entry["reset_in_seconds"]
            if (
                type(seconds) not in (int, float)
                or not math.isfinite(seconds)
                or not (seconds > 0 or (seconds == 0 and remaining == 1))
            ):
                continue
        used = percentage((1.0 - remaining) * 100.0)
        if used:
            rows.append(f"{printable(clamp(bucket))} {used} used")
    return " · ".join(rows) if rows else None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    workspace = data.get("workspace")
    cwd = (workspace.get("current_dir") if isinstance(workspace, dict) else None) or data.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = None
    parts = []
    host = host_label(socket.gethostname())
    if host:
        parts.append(host)
    home = os.path.expanduser("~")
    if cwd:
        worktree, branch = git_labels(cwd)
        parts.append(folder(cwd, home, scratch_roots(home), worktree))
        if branch:
            parts.append(branch_label(branch))
    model = model_label(data)
    if model:
        parts.append(model)
    identity = identity_label(data)
    if identity:
        parts.append(identity)
    context = context_label(data)
    if context:
        parts.append(context)
    quota = quota_label(data, datetime.now(timezone.utc))
    if quota:
        parts.append(quota)
    if parts:
        print(" | ".join(parts))


if __name__ == "__main__":
    main()

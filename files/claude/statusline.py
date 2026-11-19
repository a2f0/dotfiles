#!/usr/bin/env python3
"""Claude Code status line: the working folder and weekly cap utilization.

Claude Code pipes session JSON to stdin and shows what this prints. Mirrors
OMP's default `path` segment: a linked Git worktree shows its project name,
temporary directories show their scratch-relative path, `~/Projects`,
`~/repos`, and `/work` prefixes are dropped, the home directory becomes `~`,
and paths longer than 40 characters keep their end. The folder is a file link.
"""

import json
from datetime import datetime, timezone
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_LENGTH = 40
FOLDER, SCRATCH, WORKTREE = "📁", "🗑", "🌳"


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


def worktree_label(cwd):
    """Name a linked worktree by its project, adding the directory when it is not the branch."""
    try:
        result = subprocess.run(
            [
                "git", "-C", cwd, "rev-parse", "--absolute-git-dir",
                "--path-format=absolute", "--git-common-dir", "--show-toplevel",
                "--abbrev-ref", "HEAD",
            ],
            capture_output=True, text=True, timeout=2, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = result.stdout.splitlines()
    if len(lines) != 4 or lines[0] == lines[1]:
        return None
    _, common_dir, root, branch = lines
    # A bare repository's worktrees share `name.git` itself as the project.
    primary = os.path.dirname(common_dir) if os.path.basename(common_dir) == ".git" else common_dir
    project = os.path.basename(primary)
    if project.endswith(".git"):
        project = project[:-len(".git")]
    if not project:
        return None
    directory = os.path.basename(root)
    return project if branch == directory else f"{project}/{directory}"


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


def folder(cwd, home, scratch, worktree=None):
    if worktree:
        icon, text = WORKTREE, worktree
    else:
        icon, text = display_path(cwd, home, scratch)
        text = abbreviate_home(text, home)
    text = "".join(char if char.isprintable() else "?" for char in clamp(text))
    return f"{icon} \x1b]8;;{Path(cwd).as_uri()}\x07{text}\x1b]8;;\x07"


def percentage(value):
    if type(value) in (int, float) and 0 <= value <= 100:
        return f"{value:.0f}%"
    return None


def cached_weekly_usage(path, now):
    """Read the current account's last /usage snapshot, dropping reset windows."""
    try:
        with path.open(encoding="utf-8") as source:
            config = json.load(source)
        cache = config["cachedUsageUtilization"]
        if not cache["accountUuid"] or cache["accountUuid"] != config["oauthAccount"]["accountUuid"]:
            return {}
        age = now.timestamp() - cache["fetchedAtMs"] / 1000
        rows = cache["utilization"]["limits"]
        if not 0 <= age < 7 * 86400 or not isinstance(rows, list):
            return {}
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return {}

    minutes = int(age // 60)
    age_label = f"{minutes}m ago" if minutes < 60 else f"{minutes // 60}h ago"
    usage = {}
    for row in rows:
        try:
            if row["kind"] == "weekly_all":
                label = "All"
            elif row["kind"] == "weekly_scoped":
                if row["scope"]["model"]["display_name"].partition(" ")[0] != "Fable":
                    continue
                label = "Fable"
            else:
                continue
            reset = datetime.fromisoformat(row["resets_at"].replace("Z", "+00:00"))
            used = percentage(row["percent"])
            if used and reset > now:
                usage[label] = f"{used} used ({age_label})"
        except (AttributeError, KeyError, ValueError, TypeError):
            continue
    return usage


def main():
    data = json.load(sys.stdin)
    cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd")
    parts = []
    if cwd:
        home = os.path.expanduser("~")
        parts.append(folder(cwd, home, scratch_roots(home), worktree_label(cwd)))

    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home())
    weekly = cached_weekly_usage(config_dir / ".claude.json", datetime.now(timezone.utc))
    window = (data.get("rate_limits") or {}).get("seven_day") or {}
    live = percentage(window.get("used_percentage"))
    if live:
        weekly["All"] = f"{live} used"
    if weekly:
        parts.append("7d " + " · ".join(f"{label} {used}" for label, used in weekly.items()))
    if parts:
        print(" | ".join(parts))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Claude Code status line: the working folder, rendered like OMP's path segment.

Claude Code pipes session JSON to stdin and shows what this prints. Mirrors
OMP's default `path` segment: a linked Git worktree shows its project name,
temporary directories show their scratch-relative path, `~/Projects`,
`~/repos`, and `/work` prefixes are dropped, the home directory becomes `~`,
and paths longer than 40 characters keep their end. The folder is a file link.
"""

import json
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


def main():
    data = json.load(sys.stdin)
    cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd")
    if cwd:
        home = os.path.expanduser("~")
        print(folder(cwd, home, scratch_roots(home), worktree_label(cwd)))


if __name__ == "__main__":
    main()

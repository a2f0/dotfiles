#!/usr/bin/env python3
"""Claude Code status line: the working folder, the active model and its
effort level, the Claude identity (any `CLAUDE_CONFIG_DIR` and the session's
signed-in email), and weekly cap utilization.

Claude Code pipes session JSON to stdin and shows what this prints. Mirrors
OMP's default `path` segment: a linked Git worktree shows its project name,
temporary directories show their scratch-relative path, `~/Projects`,
`~/repos`, and `/work` prefixes are dropped, the home directory becomes `~`,
and paths longer than 40 characters keep their end. The folder is a file link.
"""

import json
from datetime import datetime, timezone
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_LENGTH = 40
FOLDER, SCRATCH, WORKTREE, CONFIG, MODEL = "📁", "🗑", "🌳", "⚙", "🤖"


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
    return f"{icon} \x1b]8;;{Path(cwd).as_uri()}\x07{text}\x1b]8;;\x07"


def text_field(data, section, key):
    """Return a non-empty string at `data[section][key]`, or None."""
    value = data.get(section)
    value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, str) and value else None


def model_label(data):
    """Name the session's model and, when the model supports one, its effort level.

    An effort level alone names nothing, so a missing model hides the segment.
    """
    model = text_field(data, "model", "display_name") or text_field(data, "model", "id")
    if not model:
        return None
    effort = text_field(data, "effort", "level")
    names = [model, effort] if effort else [model]
    return f"{MODEL} " + " · ".join(printable(clamp(name)) for name in names)


def identity_label(config_home, home, email=None):
    """Name a `CLAUDE_CONFIG_DIR` override and the signed-in email in one segment."""
    names = [abbreviate_home(config_home, home)] if config_home else []
    if email:
        names.append(email)
    if not names:
        return None
    return f"{CONFIG} " + " · ".join(printable(clamp(name)) for name in names)


def read_state(path):
    """Parse Claude's `.claude.json`, or return None when it is unreadable."""
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, ValueError):
        return None


def signed_in_email(state, session_account):
    """Return the config's signed-in email only when that account owns this session.

    `.claude.json` records the latest `/login` in its directory, which another
    session sharing the directory may have changed.
    """
    if not session_account:
        return None
    try:
        account = state["oauthAccount"]
        email = account["emailAddress"]
        owns = account["accountUuid"] == session_account
    except (KeyError, TypeError):
        return None
    return email if owns and isinstance(email, str) and email else None


def percentage(value):
    if type(value) in (int, float) and 0 <= value <= 100:
        return f"{value:.0f}%"
    return None


def live_usage(window, now):
    if not isinstance(window, dict):
        return None
    if "resets_at" in window:
        reset = window["resets_at"]
        if type(reset) not in (int, float) or not reset > now.timestamp():
            return None
    return percentage(window.get("used_percentage"))


def session_account(data):
    account = os.environ.get("CLAUDE_CODE_ACCOUNT_UUID")
    if account:
        return account
    # Claude stamps compact session-owner records throughout its JSONL transcript.
    # Bound redraw I/O and decode only the last complete owner record.
    session_id = data.get("session_id")
    transcript = data.get("transcript_path")
    if not session_id or not transcript:
        return None
    try:
        with open(transcript, "rb") as source:
            size = source.seek(0, os.SEEK_END)
            offset = max(0, size - 1024 * 1024)
            source.seek(offset)
            tail = source.read(1024 * 1024)
        if offset:
            tail = tail.partition(b"\n")[2]
        # Only newline-terminated records have finished appending.
        for line in reversed(tail.split(b"\n")[:-1]):
            if b'"session-owner"' not in line:
                continue
            owner = json.loads(line)
            if isinstance(owner, dict) and owner.get("type") == "session-owner" and owner.get("sessionId") == session_id:
                return owner.get("accountUuid")
    except (OSError, TypeError, ValueError):
        pass
    return None


def cached_weekly_usage(state, now, session_account):
    """Read the current account's last /usage snapshot, dropping reset windows."""
    if not session_account:
        return {}
    try:
        cache = state["cachedUsageUtilization"]
        account = cache["accountUuid"]
        if not account or account != state["oauthAccount"]["accountUuid"]:
            return {}
        if account != session_account:
            return {}
        age = now.timestamp() - cache["fetchedAtMs"] / 1000
        rows = cache["utilization"]["limits"]
        if not 0 <= age < 7 * 86400 or not isinstance(rows, list):
            return {}
    except (KeyError, TypeError, OverflowError):
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
            # Python 3.9 accepts only three or six fractional-second digits.
            stamp = re.sub(r"\.(\d+)", lambda m: "." + m[1][:6].ljust(6, "0"), row["resets_at"])
            reset = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
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
    home = os.path.expanduser("~")
    if cwd:
        parts.append(folder(cwd, home, scratch_roots(home), worktree_label(cwd)))
    model = model_label(data)
    if model:
        parts.append(model)
    config_home = os.environ.get("CLAUDE_CONFIG_DIR")
    account = session_account(data)
    state = read_state(Path(config_home or home) / ".claude.json") if account else None
    identity = identity_label(config_home, home, signed_in_email(state, account))
    if identity:
        parts.append(identity)

    now = datetime.now(timezone.utc)
    limits = data.get("rate_limits")
    if isinstance(limits, dict):
        live = live_usage(limits.get("seven_day"), now)
        if live or live_usage(limits.get("five_hour"), now):
            weekly = cached_weekly_usage(state, now, account)
            if live:
                parts.append(f"7d All {live} used")
                weekly.pop("All", None)
            if weekly:
                parts.append("Account 7d " + " · ".join(f"{label} {used}" for label, used in weekly.items()))
    if parts:
        print(" | ".join(parts))


if __name__ == "__main__":
    main()

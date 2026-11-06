"""SSH titles follow the remote directory without allowing terminal injection."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ZSHRC = Path(__file__).resolve().parent.parent / "files" / "zshrc"
PROMPT_HOOKS = 'for hook in "${precmd_functions[@]}"; do "$hook"; done'


class ZshTitleTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name).resolve()
        # Isolate the shipped zshrc from personal aliases and private functions.
        for name in (
            ".aliases", ".aliases-private", ".functions-posix",
            ".functions-zsh", ".quick",
        ):
            (self.home / name).touch()
        self.env = {
            "HOME": str(self.home),
            "ZDOTDIR": str(self.home),
            "PATH": "/usr/bin:/bin",
            "TERM": "xterm-ghostty",
            "ZSHRC": str(ZSHRC),
        }

    def run_shell(self, commands, *, ssh=True, **env):
        result = subprocess.run(
            [
                "zsh", "-dfi", "-c",
                'typeset -a precmd_functions\n'
                'source "$ZSHRC"; HOST=remote.example\n' + commands,
            ],
            env={**self.env, **({"SSH_TTY": "/dev/pts/test"} if ssh else {}), **env},
            cwd=self.home,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def title(self, path):
        return f"\x1b]2;remote: {path}\x07".encode()

    def test_titles_follow_directory_changes(self):
        project = self.home / "project with spaces"
        nested = project / "nested"
        nested.mkdir(parents=True)
        output = self.run_shell(
            f'{PROMPT_HOOKS}\ncd "$PROJECT"\n{PROMPT_HOOKS}\n'
            f'cd nested\n{PROMPT_HOOKS}',
            PROJECT=str(project),
        )
        self.assertEqual(
            output, self.title(self.home) + self.title(project) + self.title(nested)
        )

    def test_control_characters_cannot_inject_a_title(self):
        name = "caf\u00e9 %s\a\x1b]2;INJECTED\a\x1b\\\u009b\u009c\n"
        # Keep ordinary Unicode, percent signs, and literal backslashes intact.
        directory = self.home / name
        directory.mkdir()
        output = self.run_shell(
            f'cd "$DIRECTORY"\n{PROMPT_HOOKS}', DIRECTORY=str(directory)
        )
        self.assertEqual(output, self.title(self.home / "caf\u00e9 %s]2;INJECTED\\"))

    def test_non_ssh_shell_leaves_terminal_title_unchanged(self):
        output = self.run_shell(PROMPT_HOOKS, ssh=False)
        self.assertEqual(output, b"")


if __name__ == "__main__":
    unittest.main()

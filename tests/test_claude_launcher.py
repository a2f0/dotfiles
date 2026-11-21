"""The `claude2` function runs Claude Code with the second configuration directory."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

FUNCTIONS = Path(__file__).resolve().parents[1] / "files" / "shellcheck" / "functions"
# The stub reports the directory and every argument on its own line.
STUB = '#!/bin/sh\nprintf "%s\\n" "dir=${CLAUDE_CONFIG_DIR-unset}" "$@"\n'


class ClaudeLauncherTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name).resolve()
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "claude"
        stub.write_text(STUB)
        stub.chmod(0o755)
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "FUNCTIONS": str(FUNCTIONS),
        }

    def run_shell(self, shell, commands):
        result = subprocess.run(
            [shell, "-c", '. "$FUNCTIONS"\n' + commands],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def test_selects_the_second_directory_for_one_command(self):
        for shell in ("sh", "bash", "zsh"):
            # Resolve from the runner's PATH; the shell runs with a minimal one.
            path = shutil.which(shell)
            if not path:
                continue
            with self.subTest(shell=shell):
                self.assertEqual(
                    self.run_shell(
                        path,
                        # A `claude` function must not intercept the launcher.
                        'claude () { echo intercepted; }\n'
                        "claude2 --resume 'two words' ''\n"
                        'echo "after=${CLAUDE_CONFIG_DIR-unset}"',
                    ),
                    [
                        f"dir={self.home}/.claude2", "--resume", "two words", "",
                        "after=unset",
                    ],
                )


if __name__ == "__main__":
    unittest.main()

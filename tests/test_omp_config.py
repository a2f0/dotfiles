"""OMP's writable config must not fight Git ignores or formatting hooks."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class OmpConfigTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.env = os.environ | {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(name, None)
        self.command("git", "init", "--quiet")
        for name in (".gitignore", ".pre-commit-config.yaml"):
            shutil.copy2(REPO / name, self.root / name)
        self.command("git", "add", "--force", ".gitignore", ".pre-commit-config.yaml")
        self.config = self.root / "files/omp/config.yml"
        self.config.parent.mkdir(parents=True)
        # OMP's serializer omits the final newline, even after an unchanged save.
        self.native_config = (REPO / "files/omp/config.yml").read_bytes().rstrip(b"\n")
        self.config.write_bytes(self.native_config)

    def command(self, *args, check=True):
        return subprocess.run(
            args, cwd=self.root, env=self.env, check=check,
            capture_output=True, text=True, timeout=120,
        )

    def test_only_the_runtime_lock_is_ignored(self):
        self.config.with_name("config.yml.lock").touch()
        self.config.with_name("unrelated.lock").touch()
        result = self.command("git", "ls-files", "--others", "--exclude-standard")
        self.assertEqual(set(result.stdout.splitlines()), {
            "files/omp/config.yml", "files/omp/unrelated.lock",
        })

    def test_hook_preserves_native_omp_output_but_fixes_other_yaml(self):
        other = self.config.with_name("local.yml")
        other.write_bytes(b"enabled: true")
        self.command("git", "add", "files/omp/config.yml", "files/omp/local.yml")
        result = self.command(
            sys.executable, "-m", "pre_commit", "run", "end-of-file-fixer",
            "--files", "files/omp/config.yml", "files/omp/local.yml", check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.config.read_bytes(), self.native_config)
        self.assertEqual(other.read_bytes(), b"enabled: true\n")


if __name__ == "__main__":
    unittest.main()

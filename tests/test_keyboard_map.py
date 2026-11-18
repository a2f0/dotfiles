import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class KeyboardMapTest(unittest.TestCase):
    def test_script_selects_its_own_keyboard_map(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="keyboard test ") as directory:
            caller = Path(directory).resolve()
            checkout = caller / "checkouts" / "my dotfiles"
            script = checkout / "files/shellcheck/kb.sh"
            script.parent.mkdir(parents=True)
            shutil.copy2(source / "files/shellcheck/kb.sh", script)
            (checkout / "files/Xmodmap-Das-Keyboard-Mac").touch()
            for name, body in {
                "xset": "exit 0",
                "lsusb": "echo 'Metadot Das Keyboard'",
                "xmodmap": 'test "$#" -eq 1 && test -f "$1" && realpath -- "$1"',
            }.items():
                stub = caller / name
                stub.write_text("#!/bin/sh\n" + body + "\n")
                stub.chmod(0o755)
            env = {**os.environ, "HOME": str(caller), "PATH": os.pathsep.join([directory, os.environ["PATH"]])}
            for cwd in [checkout, caller]:
                with self.subTest(cwd=cwd):
                    result = subprocess.check_output(
                        [os.path.relpath(script, cwd)], cwd=cwd, env=env, text=True
                    )
                    self.assertEqual(result.splitlines()[-1], str(checkout / "files/Xmodmap-Das-Keyboard-Mac"))

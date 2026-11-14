"""macOS top opens in Ghostty even though it ignores user terminfo."""

import fcntl
import os
from pathlib import Path
import platform
import pty
import select
import signal
import struct
import subprocess
import termios
import time
import unittest

ALIASES = Path(__file__).resolve().parent.parent / "files" / "shellcheck" / "aliases"


@unittest.skipUnless(platform.system() == "Darwin", "the top alias is macOS-only")
class TopTerminfoTests(unittest.TestCase):
    def test_top_opens_in_ghostty(self):
        primary, secondary = pty.openpty()
        self.addCleanup(os.close, primary)
        fcntl.ioctl(secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        process = subprocess.Popen(
            # Aliases apply to later parses, as at an interactive prompt.
            ["zsh", "-df", "-c", 'source "$ALIASES"; eval top'],
            stdin=secondary,
            stdout=secondary,
            stderr=secondary,
            env={
                "ALIASES": str(ALIASES),
                "PATH": "/usr/bin:/bin",
                "TERM": "xterm-ghostty",
            },
            start_new_session=True,
        )
        os.close(secondary)

        def stop():
            # macOS refuses to signal a group that holds only a zombie.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()

        self.addCleanup(stop)

        output = b""
        deadline = time.monotonic() + 10
        while b"Processes:" not in output and time.monotonic() < deadline:
            if select.select([primary], [], [], 0.1)[0]:
                try:
                    chunk = os.read(primary, 65536)
                except OSError:  # top exited and closed the terminal
                    break
                if not chunk:
                    break
                output += chunk

        self.assertIn(b"Processes:", output, output)


if __name__ == "__main__":
    unittest.main()

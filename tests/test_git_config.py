"""Git reaches GitHub only over SSH, through ssh.github.com on port 443."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

FILES = Path(__file__).resolve().parent.parent / "files"

# GitHub's published SSH host key fingerprints
# (https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints).
GITHUB_FINGERPRINTS = {
    "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU",
    "SHA256:p2QAMXNIC1TJYWeIOttrVc98/R1BUFWu3/LiyKgUfQM",
    "SHA256:uNiVztksCsDhcc0u9e8BujQXVUpKZIDTMczCvj3tD2s",
}


class GitConfigTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name).resolve()
        self.config_dir = self.home / ".config" / "git"
        self.config_dir.mkdir(parents=True)
        (self.config_dir / "ssh_config").symlink_to(FILES / "git-ssh_config")
        (self.config_dir / "github_known_hosts").symlink_to(
            FILES / "github_known_hosts"
        )
        # The helper Xcode's system gitconfig sets on macOS.
        system = self.home / "system-gitconfig"
        system.write_text("[credential]\n\thelper = osxkeychain\n")
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_") and key != "SSH_AUTH_SOCK"
        }
        self.env.update(
            HOME=str(self.home),
            GIT_CONFIG_GLOBAL=str(FILES / "gitconfig"),
            GIT_CONFIG_SYSTEM=str(system),
            GIT_TERMINAL_PROMPT="0",
        )

    def run_git(self, *args, env=None, **kwargs):
        return subprocess.run(
            ["git", *args],
            env=env or self.env,
            cwd=self.home,
            capture_output=True,
            text=True,
            check=False,
            **kwargs,
        )

    def resolve_ssh(self):
        """Run Git's SSH command as Git does, with `-G` to print its config."""
        command = self.run_git("config", "core.sshCommand").stdout.strip()
        result = subprocess.run(
            ["sh", "-c", f'{command} "$@"', command, "-G", "git@github.com"],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        values = dict(
            line.split(" ", 1) for line in result.stdout.splitlines() if " " in line
        )
        return values["hostname"], values["port"]

    def test_https_github_urls_use_ssh(self):
        for url in (
            "https://github.com/a2f0/dotfiles.git",
            "https://github.com/a2f0/dotfiles",
        ):
            result = self.run_git("ls-remote", "--get-url", url)
            self.assertEqual(
                result.stdout.strip(), url.replace("https://github.com/", "git@github.com:")
            )
        other = self.run_git("ls-remote", "--get-url", "https://gitlab.com/a/b.git")
        self.assertEqual(other.stdout.strip(), "https://gitlab.com/a/b.git")

    def test_no_credential_helper_runs_for_github(self):
        result = self.run_git(
            "credential",
            "fill",
            input="protocol=https\nhost=github.com\n\n",
            env={**self.env, "GIT_TRACE": "1"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("credential-osxkeychain", result.stderr)
        # Other hosts keep the system helper.
        other = self.run_git(
            "config", "--get-urlmatch", "credential.helper", "https://gitlab.com"
        )
        self.assertEqual(other.stdout.strip(), "osxkeychain")

    def test_ssh_reaches_github_on_port_443(self):
        self.assertEqual(self.resolve_ssh(), ("ssh.github.com", "443"))

    def test_ssh_falls_back_to_plain_ssh_until_provisioned(self):
        (self.config_dir / "ssh_config").unlink()
        self.assertEqual(self.resolve_ssh(), ("github.com", "22"))

    def test_known_hosts_pin_githubs_published_keys(self):
        result = subprocess.run(
            ["ssh-keygen", "-l", "-f", str(FILES / "github_known_hosts")],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.splitlines()
        self.assertEqual({line.split()[1] for line in lines}, GITHUB_FINGERPRINTS)
        self.assertTrue(all(line.split()[2] == "github.com" for line in lines))


if __name__ == "__main__":
    unittest.main()

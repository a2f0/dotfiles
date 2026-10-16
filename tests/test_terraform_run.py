import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform"

# Records how the wrapper ran Terraform: its directory, arguments, and the AWS
# and state variables it received.
STUB = """#!/bin/sh
{
  printf 'cwd=%s\\n' "$(pwd -P)"
  printf 'args=%s\\n' "$*"
  for name in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_PROFILE \\
      AWS_SESSION_TOKEN TF_STATE_ACCESS_KEY_ID TF_STATE_SECRET_ACCESS_KEY; do
    eval "value=\\${$name-unset}"
    printf '%s=%s\\n' "$name" "$value"
  done
} > "$TERRAFORM_LOG"
"""

APP_ENV = (
    "TF_STATE_ACCESS_KEY_ID=app-id\n"
    "TF_STATE_SECRET_ACCESS_KEY=app-secret\n"
)


class TerraformRunTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.terraform = self.root / "terraform"
        self.terraform.mkdir()
        for script in ("run.sh", "init.sh", "apply.sh"):
            shutil.copy2(TERRAFORM_DIR / script, self.terraform / script)
        self.tier = self.root / ".secrets" / "prod"
        self.tier.mkdir(parents=True)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "terraform"
        stub.write_text(STUB)
        stub.chmod(0o755)
        self.log = self.root / "terraform.log"
        self.env = {
            "HOME": str(self.root),
            "PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "TERRAFORM_LOG": str(self.log),
        }

    def write_secrets(self, app=APP_ENV, shared=None):
        if app is not None:
            (self.tier / "app.env").write_text(app)
        if shared is not None:
            (self.tier / "shared.env").write_text(shared)

    def run_script(self, script, *args, **env):
        return subprocess.run(
            [str(self.terraform / script), *args],
            cwd=self.root,
            env={**self.env, **env},
            capture_output=True,
            text=True,
            check=False,
        )

    def terraform_call(self):
        lines = self.log.read_text().splitlines()
        return dict(line.split("=", 1) for line in lines)

    def test_run_forwards_arguments_from_the_terraform_directory(self):
        self.write_secrets()
        result = self.run_script("run.sh", "plan", "-var-file=main.tfvars")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.terraform_call()
        self.assertEqual(call["cwd"], str(self.terraform))
        self.assertEqual(call["args"], "plan -var-file=main.tfvars")

    def test_init_reconfigures_without_input(self):
        self.write_secrets()
        result = self.run_script("init.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.terraform_call()["args"], "init -input=false -reconfigure"
        )

    def test_apply_uses_the_variable_file(self):
        self.write_secrets()
        result = self.run_script("apply.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.terraform_call()["args"], "apply -var-file=main.tfvars"
        )

    def test_state_key_replaces_ambient_aws_credentials(self):
        self.write_secrets()
        result = self.run_script(
            "run.sh",
            "plan",
            AWS_ACCESS_KEY_ID="ambient-id",
            AWS_SECRET_ACCESS_KEY="ambient-secret",
            AWS_PROFILE="ambient-profile",
            AWS_SESSION_TOKEN="ambient-session",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.terraform_call()
        self.assertEqual(call["AWS_ACCESS_KEY_ID"], "app-id")
        self.assertEqual(call["AWS_SECRET_ACCESS_KEY"], "app-secret")
        self.assertEqual(call["AWS_PROFILE"], "unset")
        self.assertEqual(call["AWS_SESSION_TOKEN"], "unset")

    def test_app_env_overrides_shared_env(self):
        self.write_secrets(
            shared=(
                "TF_STATE_ACCESS_KEY_ID=shared-id\n"
                "TF_STATE_SECRET_ACCESS_KEY=shared-secret\n"
            ),
            app="TF_STATE_SECRET_ACCESS_KEY=app-secret\n",
        )
        result = self.run_script("run.sh", "plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.terraform_call()
        self.assertEqual(call["AWS_ACCESS_KEY_ID"], "shared-id")
        self.assertEqual(call["AWS_SECRET_ACCESS_KEY"], "app-secret")

    def test_missing_app_env_stops_before_terraform(self):
        self.write_secrets(app=None, shared=APP_ENV)
        result = self.run_script("init.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("app.env is missing", result.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_state_variable_stops_before_terraform(self):
        self.write_secrets(app="TF_STATE_ACCESS_KEY_ID=app-id\n")
        result = self.run_script("apply.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TF_STATE_SECRET_ACCESS_KEY", result.stderr)
        self.assertNotIn("  - TF_STATE_ACCESS_KEY_ID", result.stderr)
        self.assertFalse(self.log.exists())

    def test_malformed_secrets_file_stops_before_terraform(self):
        self.write_secrets(app=APP_ENV + "not an assignment\n")
        result = self.run_script("run.sh", "plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()

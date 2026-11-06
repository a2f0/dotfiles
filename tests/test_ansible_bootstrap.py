from email.parser import Parser
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


REPO = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.wheelhouse = Path(directory.name)
        # Repack the installed, real PyYAML wheel for offline installation into
        # fresh venvs. No package index or fake Python/pip/guard is involved.
        package = distribution("PyYAML")
        cls.yaml_version = package.version
        tag = Parser().parsestr(package.read_text("WHEEL"))["Tag"]
        wheel = cls.wheelhouse / f"pyyaml-{package.version}-{tag}.whl"
        with ZipFile(wheel, "w") as archive:
            for entry in package.files:
                if ".." not in entry.parts and "__pycache__" not in entry.parts:
                    archive.write(package.locate_file(entry), str(entry))

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bootstrap test ")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.checkout = self.root / "checkout with spaces"
        self.checkout.mkdir()
        shutil.copy2(REPO / "runAnsible.sh", self.checkout)
        guard = self.checkout / "scripts/deploy/ansible_safe_run.py"
        guard.parent.mkdir(parents=True)
        shutil.copy2(REPO / "scripts/deploy/ansible_safe_run.py", guard)
        self.requirements = self.checkout / "requirements.txt"
        self.requirements.write_text(
            f"-c requirements-constraints.txt\nPyYAML=={self.yaml_version}\n"
        )
        self.constraints = self.checkout / "requirements-constraints.txt"
        self.constraints.write_text("")
        self.python = self.checkout / ".venv/bin/python3"
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("PYTHON", "PIP_")) and key != "VIRTUAL_ENV"
        }
        self.env.update(
            PATH=str(Path(sys.base_prefix) / "bin") + os.pathsep + self.env["PATH"],
            PIP_CONFIG_FILE=os.devnull,
            PIP_NO_INDEX="1",
            PIP_FIND_LINKS=str(self.wheelhouse),
        )

    def launch(self, **environment):
        return subprocess.run(
            [str(self.checkout / "runAnsible.sh"), "--help"],
            cwd=self.root,
            env={**self.env, **environment},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_fresh_bootstrap_installs_into_checkout_from_another_directory(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        probe = subprocess.run(
            [str(self.python), "-I", "-c",
             "import json, sys, yaml; print(json.dumps([sys.prefix, yaml.__file__, "
             "yaml.safe_load('enabled: true')]))"],
            capture_output=True,
            text=True,
            check=True,
        )
        prefix, module, parsed = json.loads(probe.stdout)
        self.assertEqual(Path(prefix), self.checkout / ".venv")
        self.assertTrue(Path(module).is_relative_to(Path(prefix)))
        self.assertEqual(parsed, {"enabled": True})
        self.assertFalse((self.root / ".venv").exists())

    def test_partial_environment_bootstraps_missing_pip(self):
        subprocess.run(
            [str(Path(sys.base_prefix) / "bin/python3"), "-I", "-m", "venv",
             "--without-pip", str(self.checkout / ".venv")],
            check=True,
            capture_output=True,
            text=True,
        )
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        probe = subprocess.run(
            [str(self.python), "-I", "-c",
             "import yaml; assert yaml.safe_load('enabled: true') == {'enabled': True}"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)

    def test_broken_interpreter_does_not_rewrite_existing_environment(self):
        self.python.parent.mkdir(parents=True)
        missing = self.root / "removed-python"
        self.python.symlink_to(missing)
        config = self.checkout / ".venv/pyvenv.cfg"
        config.write_text(f"home = {missing.parent}\n")
        original_config = config.read_bytes()
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config.read_bytes(), original_config)
        self.assertEqual(self.python.readlink(), missing)
        self.assertEqual(result.stdout, "")

    def test_install_failure_stops_before_guard(self):
        self.requirements.write_text("dotfiles-unavailable-test-dependency==0\n")
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No matching distribution found", result.stderr)
        self.assertEqual(result.stdout, "")
        probe = subprocess.run(
            [str(self.python), "-I", "-c",
             "import importlib.util; assert importlib.util.find_spec('yaml') is None"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)

    def test_existing_environment_cannot_bypass_changed_constraints(self):
        first = self.launch()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.constraints.write_text("PyYAML<0\n")
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ResolutionImpossible", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_bootstrap_and_guard_ignore_inherited_python_import_path(self):
        marker = self.root / "injected"
        (self.root / "sitecustomize.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "Path(os.environ['INJECTION_MARKER']).write_text('injected')\n"
        )
        result = self.launch(PYTHONPATH=str(self.root), INJECTION_MARKER=str(marker))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()

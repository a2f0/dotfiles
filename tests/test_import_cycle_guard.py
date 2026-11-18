"""Exercise the dotfiles graph configuration against invalid TypeScript imports."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class ImportCycleGuardTests(unittest.TestCase):
    def rejected_graph(self, sources):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(REPO / "agent-tool.json", root / "agent-tool.json")
            for name, source in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [REPO / "node_modules/.bin/agent-tool", "--repo", root, "graph", "check"],
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_type_only_cycle_between_extension_and_script(self):
        extension = "files/omp/extensions/status.ts"
        helper = "scripts/helper.ts"
        graph = self.rejected_graph({
            extension: 'export type { Helper } from "../../../scripts/helper";\nexport type Status = string;',
            helper: 'export type { Status } from "../files/omp/extensions/status";\nexport type Helper = number;',
        })
        self.assertIn([extension, helper], graph["cycles"])

    def test_extension_importing_a_test_fixture(self):
        extension = "files/omp/extensions/status.ts"
        fixture = "tests/fixture.ts"
        graph = self.rejected_graph({
            extension: 'export type { Fixture } from "../../../tests/fixture";',
            fixture: "export type Fixture = string;",
        })
        self.assertIn(f"{extension} imports test-only {fixture}", graph["violations"])

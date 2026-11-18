"""Exercise the dotfiles graph configuration against invalid TypeScript imports."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class ImportCycleGuardTests(unittest.TestCase):
    def check_graph(self, sources, expected_exit):
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
        self.assertEqual(result.returncode, expected_exit, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_type_only_cycle_between_extension_and_script(self):
        extension = "files/omp/extensions/status.ts"
        helper = "scripts/helper.ts"
        graph = self.check_graph({
            extension: 'export type { Helper } from "../../../scripts/helper";\nexport type Status = string;',
            helper: 'export type { Status } from "../files/omp/extensions/status";\nexport type Helper = number;',
        }, expected_exit=1)
        self.assertIn([extension, helper], graph["cycles"])

    def test_only_tests_can_import_a_test_fixture(self):
        extension = "files/omp/extensions/status.ts"
        fixture = "tests/fixture.ts"
        sources = {fixture: "export const fixture = 1;"}
        graph = self.check_graph(sources | {
            extension: 'import { fixture } from "../../../tests/fixture";\nexport const status = fixture;',
        }, expected_exit=1)
        self.assertIn(f"{extension} imports test-only {fixture}", graph["violations"])

        graph = self.check_graph(sources | {
            "tests/status.test.ts": 'import { fixture } from "./fixture";\nexport const status = fixture;',
        }, expected_exit=0)
        self.assertEqual(graph["imports"], 1)

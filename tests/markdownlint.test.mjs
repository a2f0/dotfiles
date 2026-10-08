import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { parse as parseJsonc } from "jsonc-parser";

const cli = fileURLToPath(new URL("../node_modules/markdownlint-cli2/markdownlint-cli2-bin.mjs", import.meta.url));

function fixture(t, config, markdown = "# Good\n") {
  const directory = mkdtempSync(join(tmpdir(), "dotfiles-markdownlint-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  mkdirSync(join(directory, "docs"));
  writeFileSync(join(directory, "docs/good.md"), markdown);
  writeFileSync(join(directory, "pyproject.toml"), config);
  return directory;
}

function lint(directory, glob = "docs/*.md", config = "pyproject.toml") {
  const result = spawnSync(process.execPath, [
    cli, "--config", config, "--configPointer", "/tool/markdownlint-cli2", glob,
  ], { cwd: directory, encoding: "utf8", timeout: 20000 });
  assert.ifError(result.error);
  return { status: result.status, output: result.stdout + result.stderr };
}

test("actual CLI accepts null-prototype TOML options and preserves glob ignores", (t) => {
  const directory = fixture(t, `
[tool.markdownlint-cli2]
ignores = ["docs/ignored.md"]
[tool.markdownlint-cli2.config]
default = false
MD018 = true
`);
  writeFileSync(join(directory, "docs/ignored.md"), "#Missing space\n");
  const result = lint(directory, "docs/{good,ignored}.md");
  assert.equal(result.status, 0, result.output);
  assert.match(result.output, /Linting: 1 file/);
});

test("nested TOML rule tables retain enforcement and do not weaken lint failures", (t) => {
  const directory = fixture(t, `
[tool.markdownlint-cli2.config]
default = false
[tool.markdownlint-cli2.config.MD013]
line_length = 12
headings = false
code_blocks = false
`, "# Heading is exempt\n\nThis paragraph exceeds twelve columns.\n");
  const result = lint(directory);
  assert.equal(result.status, 1, result.output);
  assert.match(result.output, /MD013\/line-length/);
  assert.match(result.output, /good\.md:3/);
  assert.doesNotMatch(result.output, /good\.md:1/);
});

test("nested TOML enabled=false retains an explicit disabled rule", (t) => {
  const directory = fixture(t, `
[tool.markdownlint-cli2.config]
default = false
[tool.markdownlint-cli2.config.MD018]
enabled = false
`, "#Missing space\n");
  const result = lint(directory);
  assert.equal(result.status, 0, result.output);
});

test("nested TOML severity behaves like ordinary JSON configuration objects", (t) => {
  const directory = fixture(t, `
[tool.markdownlint-cli2.config]
default = false
[tool.markdownlint-cli2.config.MD018]
severity = "warning"
`, "#Missing space\n");
  writeFileSync(join(directory, "config.json"), JSON.stringify({
    tool: { "markdownlint-cli2": { config: { default: false, MD018: { severity: "warning" } } } },
  }));
  const toml = lint(directory);
  const ordinary = lint(directory, "docs/*.md", "config.json");
  assert.match(ordinary.output, /MD018\/no-missing-space-atx/);
  assert.match(toml.output, /MD018\/no-missing-space-atx/);
  assert.equal(toml.status, ordinary.status);
  assert.equal(toml.output, ordinary.output);
});

test("the parser security override remains confined to its reviewed CLI owner", () => {
  const errors = [];
  const lock = parseJsonc(readFileSync(new URL("../bun.lock", import.meta.url), "utf8"), errors, { allowTrailingComma: true });
  assert.equal(errors.length, 0);
  const owners = Object.entries(lock.packages).filter(([, entry]) => entry[2]?.dependencies?.["smol-toml"]);
  assert.deepEqual(owners.map(([name]) => name), ["markdownlint-cli2"]);
  assert.equal(owners[0][1][0], "markdownlint-cli2@0.23.3");
  assert.equal(lock.packages["smol-toml"][0], "smol-toml@1.9.0");
});

test("malformed TOML remains a fatal configuration error", (t) => {
  const directory = fixture(t, "[tool.markdownlint-cli2]\nignores = [\n");
  const result = lint(directory);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /Unable to parse|invalid|Invalid|Error/i);
});

test("CLI parses many flat TOML keys through the secured parser override", (t) => {
  const keys = Array.from({ length: 32768 }, (_, index) => `key_${index} = 1`).join("\n");
  const directory = fixture(t, `${keys}\n[tool.markdownlint-cli2.config]\ndefault = false\nMD018 = true\n`);
  const result = lint(directory);
  assert.equal(result.status, 0, result.output);
  assert.match(result.output, /Linting: 1 file/);
});

test("the repository's YAML configuration keeps its existing rule scope", (t) => {
  const directory = fixture(t, "");
  writeFileSync(join(directory, ".markdownlint.yaml"), readFileSync(new URL("../.markdownlint.yaml", import.meta.url)));
  writeFileSync(join(directory, "docs/good.md"), `# Good\n\n${"Long prose ".repeat(30).trim()}\n`);
  const result = spawnSync(process.execPath, [cli, "docs/good.md"], {
    cwd: directory, encoding: "utf8", timeout: 20000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

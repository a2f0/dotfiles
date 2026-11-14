import { afterEach, expect, mock, spyOn, test } from "bun:test";
import * as os from "node:os";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import hostnameStatus from "../files/omp/extensions/hostname";

// Keep host mocking scoped to each test, including when an assertion fails.
afterEach(() => mock.restore());

function startSession(hasUI: boolean) {
  let start: (_event: unknown, ctx: unknown) => void;
  const statuses: Record<string, string> = {};
  hostnameStatus({
    on: (_event: string, handler: typeof start) => { start = handler; },
  } as unknown as ExtensionAPI);
  start!({}, {
    hasUI,
    ui: {
      setStatus: (key: string, value: string) => {
        if (!hasUI) throw new Error("Headless sessions cannot render UI");
        statuses[key] = value;
      },
    },
  });
  return statuses;
}

test.each([
  ["builder.example.net", "builder"],
  ["laptop.local", "laptop"],
  ["workstation", "workstation"],
])("shows the short hostname for %s", (hostname, expected) => {
  spyOn(os, "hostname").mockReturnValue(hostname);
  expect(startSession(true)).toEqual({ hostname: expected });
});

test("leaves headless sessions without a hostname UI status", () => {
  spyOn(os, "hostname").mockReturnValue("worker.example.net");
  expect(startSession(false)).toEqual({});
});

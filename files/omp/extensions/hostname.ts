import { hostname } from "node:os";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

export default function hostnameStatus(pi: ExtensionAPI) {
  const host = hostname().split(".")[0];

  pi.on("session_start", (_event, ctx) => {
    if (ctx.hasUI) {
      ctx.ui.setStatus("hostname", host);
    }
  });
}

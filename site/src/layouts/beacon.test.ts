import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { describe, expect, it, vi } from "vitest";

import Base from "./Base.astro";

const WORKER_URL = "https://visit-notifier.ryanpivovar.workers.dev/";

/** Render the layout and return the source of the inline visit beacon script. */
async function beaconScript(): Promise<string> {
  const container = await AstroContainer.create();
  const html = await container.renderToString(Base, {
    props: { title: "TX-35", description: "About TX-35.", path: "/tx/35" },
  });
  const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map(([, body = ""]) => body)
    .find((body) => body.includes("sendBeacon"));
  if (!script) throw new Error("no visit beacon script in the layout");
  return script;
}

/** Run the beacon script against stand-in browser globals and return the sendBeacon mock. */
function runBeacon(script: string, getItem: (key: string) => string | null) {
  const sendBeacon = vi.fn(() => true);
  const run = new Function("localStorage", "navigator", "location", "document", script) as (...args: unknown[]) => void;
  run({ getItem }, { sendBeacon }, { pathname: "/tx/35" }, { referrer: "https://news.example/item?id=1" });
  return sendBeacon;
}

describe("visit beacon", () => {
  it("sends the page path and referrer to the visit-notifier Worker as a plain string", async () => {
    const sendBeacon = runBeacon(await beaconScript(), () => null);
    expect(sendBeacon).toHaveBeenCalledTimes(1);
    expect(sendBeacon).toHaveBeenCalledWith(
      WORKER_URL,
      JSON.stringify({ path: "/tx/35", ref: "https://news.example/item?id=1" }),
    );
  });

  it("stays silent in a browser with no-visit-ping set", async () => {
    const sendBeacon = runBeacon(await beaconScript(), (key) => (key === "no-visit-ping" ? "1" : null));
    expect(sendBeacon).not.toHaveBeenCalled();
  });

  it("stays silent, without throwing, when storage is blocked", async () => {
    const script = await beaconScript();
    const sendBeacon = runBeacon(script, () => {
      throw new Error("SecurityError");
    });
    expect(sendBeacon).not.toHaveBeenCalled();
  });
});

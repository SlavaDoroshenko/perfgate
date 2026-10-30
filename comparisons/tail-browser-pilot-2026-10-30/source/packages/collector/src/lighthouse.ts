import * as chromeLauncher from "chrome-launcher";
import lighthouse from "lighthouse";

import type { LhrLike } from "./extract.js";
import type { Throttling } from "./schema.js";

const THROTTLING_METHOD = {
  simulate: "simulate",
  devtools: "devtools",
  none: "provided",
} as const;

/**
 * One cold page load: a fresh Chrome with a throwaway profile per call,
 * so caches and service workers never leak between runs.
 */
export async function measure(url: string, throttling: Throttling): Promise<LhrLike> {
  const chrome = await chromeLauncher.launch({
    chromeFlags: ["--headless=new", "--no-sandbox", "--disable-gpu"],
  });
  try {
    const result = await lighthouse(url, {
      port: chrome.port,
      output: "json",
      logLevel: "error",
      onlyCategories: ["performance"],
      throttlingMethod: THROTTLING_METHOD[throttling],
    });
    if (!result) throw new Error("lighthouse returned no result");
    return result.lhr as unknown as LhrLike;
  } finally {
    await chrome.kill();
  }
}

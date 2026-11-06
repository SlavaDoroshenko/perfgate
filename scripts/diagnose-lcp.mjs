/** Exploratory LCP waterfall capture; deliberately separate from frozen gate/collector.
 *
 * Same protocol as a candidate job (fresh Chrome per load, devtools throttling, ABAB,
 * warmups), but every load keeps the LCP element and the timing of every request, so a
 * job whose sides differ can be traced to the request that moved.
 */
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { parseArgs } from "node:util";

const require = createRequire(new URL("../packages/collector/package.json", import.meta.url));
const { default: lighthouse } = await import(pathToFileURL(require.resolve("lighthouse")).href);
const chromeLauncher = await import(pathToFileURL(require.resolve("chrome-launcher")).href);
const { values } = parseArgs({ options: {
  url: { type: "string" }, "pr-url": { type: "string" }, out: { type: "string" },
  runs: { type: "string", default: "20" }, warmup: { type: "string", default: "2" },
} });
const runs = Number(values.runs), warmup = Number(values.warmup);
if (!values.url || !values["pr-url"] || !values.out || !Number.isInteger(runs) || runs < 1 ||
    !Number.isInteger(warmup) || warmup < 0 || !process.env.CHROME_PATH) {
  throw new Error("Required: --url URL --pr-url URL --out NEW_DIR; positive --runs, nonnegative --warmup and CHROME_PATH");
}
const out = resolve(values.out);
await mkdir(out); // refuse to overwrite an existing experiment

async function load(url) {
  const chrome = await chromeLauncher.launch({ chromeFlags: ["--headless=new", "--no-sandbox", "--disable-gpu"] });
  try {
    const result = await lighthouse(url, { port: chrome.port, output: "json", logLevel: "error",
      onlyCategories: ["performance"], throttlingMethod: "devtools" });
    const audits = result.lhr.audits;
    // Lighthouse 13: the LCP element and its subparts live in the breakdown insight
    const parts = audits["lcp-breakdown-insight"]?.details?.items ?? [];
    const node = parts.find((p) => p.type === "node");
    const subparts = Object.fromEntries((parts.find((p) => p.type === "table")?.items ?? [])
      .map((x) => [x.subpart, x.duration]));
    return {
      lcp: audits["largest-contentful-paint"].numericValue,
      fcp: audits["first-contentful-paint"].numericValue,
      lcp_element: node ? { selector: node.selector, snippet: node.snippet } : null,
      lcp_subparts: subparts,
      requests: (audits["network-requests"]?.details?.items ?? [])
        .filter((r) => !r.url.startsWith("data:"))
        .map((r) => ({ path: new URL(r.url).pathname, start: r.networkRequestTime, end: r.networkEndTime,
                       bytes: r.transferSize, type: r.resourceType, priority: r.priority, protocol: r.protocol,
                       status: r.statusCode })),
    };
  } finally {
    await chrome.kill();
  }
}

for (let i = 0; i < warmup; i++) await load(values.url);
const rows = [];
for (let i = 0; i < runs; i++) {
  for (const [variant, url] of [["base", values.url], ["pr", values["pr-url"]]]) {
    rows.push({ variant, run_index: i, order: rows.length, ...(await load(url)) });
    process.stderr.write(`${variant} ${i}: LCP ${Math.round(rows.at(-1).lcp)} ms\n`);
  }
}
await writeFile(resolve(out, "loads.json"), JSON.stringify(rows, null, 1) + "\n");

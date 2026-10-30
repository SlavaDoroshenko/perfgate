/** Exploratory trace capture; deliberately separate from frozen gate/collector. */
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";

const require = createRequire(new URL("../packages/collector/package.json", import.meta.url));
const { default: lighthouse } = await import(pathToFileURL(require.resolve("lighthouse")).href);
const chromeLauncher = await import(pathToFileURL(require.resolve("chrome-launcher")).href);
const { values } = parseArgs({ options: {
  url: { type: "string" }, "pr-url": { type: "string" }, out: { type: "string" },
  pairs: { type: "string", default: "4" }, warmup: { type: "string", default: "2" },
} });
const pairs = Number(values.pairs), warmup = Number(values.warmup);
if (!values.url || !values["pr-url"] || !values.out || !Number.isInteger(pairs) || pairs < 1 ||
    !Number.isInteger(warmup) || warmup < 0 || !process.env.CHROME_PATH) {
  throw new Error("Required: --url URL --pr-url URL --out NEW_DIR; positive --pairs, nonnegative --warmup and CHROME_PATH");
}
for (const url of [values.url, values["pr-url"]]) {
  const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`Readiness failed: HTTP ${response.status} for ${url}`);
  await response.arrayBuffer();
}
const out = resolve(values.out);
await mkdir(out); // Refuse to overwrite an existing experiment.
const manifest = {
  purpose: "exploratory CLS trace diagnosis, not confirmatory gate evaluation",
  source: execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
  chrome: execFileSync(process.env.CHROME_PATH, ["--version"], { encoding: "utf8" }).trim(),
  script_sha256: createHash("sha256").update(await readFile(new URL(import.meta.url))).digest("hex"),
  pairs, warmup, started: new Date().toISOString(), runs: [],
};
await writeFile(`${out}/manifest.json`, JSON.stringify(manifest, null, 2) + "\n");
for (let index = -warmup; index < pairs; index++) {
  for (const [variant, url] of [["base", values.url], ["pr", values["pr-url"]]]) {
    const chrome = await chromeLauncher.launch({ chromeFlags: ["--headless=new", "--no-sandbox", "--disable-gpu"] });
    try {
      const result = await lighthouse(url, { port: chrome.port, output: "json", logLevel: "error",
        onlyCategories: ["performance"], throttlingMethod: "devtools" });
      if (!result || result.lhr.runtimeError) throw new Error(JSON.stringify(result?.lhr.runtimeError));
      const { lhr, artifacts } = result;
      const prefix = `${index < 0 ? "warmup" : "run"}-${Math.abs(index)}-${variant}`;
      const trace = artifacts.Trace;
      const shifts = trace.traceEvents.filter(e => e.name === "LayoutShift");
      const row = { index, variant, url, timestamp: new Date().toISOString(),
        cls: lhr.audits["cumulative-layout-shift"].numericValue,
        fcp: lhr.audits["first-contentful-paint"].numericValue,
        lcp: lhr.audits["largest-contentful-paint"].numericValue,
        tbt: lhr.audits["total-blocking-time"].numericValue,
        shifts, traceElements: artifacts.TraceElements,
      };
      await writeFile(`${out}/${prefix}.json`, JSON.stringify(row, null, 2) + "\n");
      await writeFile(`${out}/${prefix}.trace.json.gz`, gzipSync(JSON.stringify(trace)));
      await writeFile(`${out}/${prefix}.lhr.json.gz`, gzipSync(JSON.stringify(lhr)));
      manifest.runs.push({ file: `${prefix}.json`, index, variant, cls: row.cls });
      await writeFile(`${out}/manifest.json`, JSON.stringify(manifest, null, 2) + "\n");
      console.log(prefix, "CLS", row.cls, "shifts", shifts.map(e => e.args.data?.score));
    } catch (error) {
      manifest.failure = { index, variant, timestamp: new Date().toISOString(), error: String(error) };
      await writeFile(`${out}/manifest.json`, JSON.stringify(manifest, null, 2) + "\n");
      throw error;
    } finally { await chrome.kill(); }
  }
}
manifest.finished = new Date().toISOString();
await writeFile(`${out}/manifest.json`, JSON.stringify(manifest, null, 2) + "\n");

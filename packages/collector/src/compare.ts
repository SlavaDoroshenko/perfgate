import { spawnSync } from "node:child_process";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { parseArgs } from "node:util";

export async function compare(argv: string[]): Promise<void> {
  const { values } = parseArgs({ args: argv, strict: true, options: {
    url: { type: "string" }, "pr-url": { type: "string" }, input: { type: "string" },
    runs: { type: "string", default: "20" }, out: { type: "string" },
    app: { type: "string", default: "web" }, "app-build": { type: "string" }, label: { type: "string" },
  } });
  const runs = Number(values.runs);
  if (![10, 20].includes(runs)) throw new Error("compare requires --runs 10 or 20");
  if (!values.out) throw new Error("compare requires --out <new directory>");
  if (values.input ? Boolean(values.url || values["pr-url"]) : !(values.url && values["pr-url"])) {
    throw new Error("provide either --input <JSONL> or both --url and --pr-url");
  }
  const root = resolve(import.meta.dirname, "../../..");
  const python = process.env.PERFGATE_PYTHON ?? resolve(root, "analysis/.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const env = { ...process.env, PYTHONPATH: [resolve(root, "analysis"), process.env.PYTHONPATH].filter(Boolean).join(process.platform === "win32" ? ";" : ":") };
  // Check the analysis environment before spending minutes measuring pages.
  const check = spawnSync(python, ["-c", "import perfgate_analysis.compare"], { env, encoding: "utf8" });
  if (check.error || check.status !== 0) throw new Error(`Python analysis unavailable; run uv sync --locked --directory analysis or set PERFGATE_PYTHON. ${check.error?.message ?? check.stderr}`);
  const out = resolve(values.out);
  await mkdir(out, { recursive: true });
  if ((await readdir(out)).length) throw new Error("--out must be empty; previous reports must not be reused");
  const input = values.input ? resolve(values.input) : resolve(out, "runs.jsonl");
  const start = performance.now();
  let collectStatus: number | null = null;
  if (!values.input) {
    const args = [...process.execArgv, process.argv[1]!, "collect", "--url", values.url!, "--pr-url", values["pr-url"]!,
      "--runs", String(runs), "--mode", "abab", "--throttling", "devtools", "--warmup", "2", "--app", values.app!,
      "--label", values.label ?? (values.url === values["pr-url"] ? "aa" : "commit"), "--out", input];
    if (values["app-build"]) args.push("--app-build", values["app-build"]);
    const collect = spawnSync(process.execPath, args, { env, stdio: "inherit" });
    if (collect.error) throw collect.error;
    collectStatus = collect.status;
  }
  const collectionSeconds = (performance.now() - start) / 1000;
  const analysisStart = performance.now();
  const report = spawnSync(python, ["-m", "perfgate_analysis.compare", input, "--runs", String(runs), "--out", out], { env, stdio: "inherit" });
  await writeFile(resolve(out, "execution.json"), JSON.stringify({
    measured: !values.input, collector_exit: collectStatus, collection_seconds: values.input ? null : collectionSeconds,
    analysis_seconds: (performance.now() - analysisStart) / 1000,
    total_seconds: (performance.now() - start) / 1000, input,
  }, null, 2) + "\n");
  if (report.error) throw report.error;
  process.exitCode = report.status ?? 3;
  if (!values.input && collectStatus !== 0 && process.exitCode < 2) process.exitCode = 2;
  process.stderr.write(`report: ${resolve(out, "comparison.md")}\n`);
}

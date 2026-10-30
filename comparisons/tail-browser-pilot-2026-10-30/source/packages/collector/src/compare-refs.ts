import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { z } from "zod";
import { compare } from "./compare.js";

const Command = z.array(z.string()).min(1);
export const RefConfig = z.object({
  install: Command.optional(), build: Command.optional(), start: Command,
  path: z.string().default("/"), readyPath: z.string().default("/"),
  app: z.string().default("web"), startupTimeoutMs: z.number().int().positive().default(60000),
  buildTimeoutMs: z.number().int().positive().default(600000),
}).strict();

async function freePort(): Promise<number> {
  const server = createServer();
  return new Promise((accept, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") return reject(new Error("cannot reserve port"));
      server.close(() => accept(address.port));
    });
  });
}

export async function compareRefs(argv: string[]): Promise<void> {
  const { values } = parseArgs({ args: argv, strict: true, options: {
    repo: { type: "string", default: process.cwd() }, "base-ref": { type: "string" },
    "pr-ref": { type: "string" }, config: { type: "string" }, out: { type: "string" },
    runs: { type: "string", default: "20" },
  } });
  if (!values["base-ref"] || !values["pr-ref"] || !values.config || !values.out || !["10", "20"].includes(values.runs!)) {
    throw new Error("compare-refs requires --base-ref, --pr-ref, --config, --out and --runs 10|20");
  }
  const repo = resolve(values.repo!);
  const config = RefConfig.parse(JSON.parse(await readFile(resolve(values.config), "utf8")));
  for (const path of [config.path, config.readyPath]) {
    if (!path.startsWith("/") || path.startsWith("//")) throw new Error("config paths must be local absolute URL paths");
  }
  const out = resolve(values.out); await mkdir(out, { recursive: true });
  if ((await readdir(out)).length) throw new Error("--out must be empty");
  function git(args: string[]) {
    const result = spawnSync("git", ["-C", repo, ...args], { encoding: "utf8" });
    if (result.error || result.status !== 0) throw new Error(result.error?.message ?? result.stderr);
    return result.stdout.trim();
  }
  const refs = [values["base-ref"], values["pr-ref"]].map(ref => git(["rev-parse", "--verify", "--end-of-options", `${ref}^{commit}`]));
  const temp = await mkdtemp(resolve(tmpdir(), "perfgate-refs-"));
  const worktrees: string[] = [], servers: ChildProcess[] = [];
  const timings: Record<string, number> = {};
  const started = performance.now();
  try {
    const ports: number[] = [];
    for (const [index, side] of ["base", "pr"].entries()) {
      const worktree = resolve(temp, side); git(["worktree", "add", "--detach", worktree, refs[index]!]); worktrees.push(worktree);
      let port = await freePort(); while (ports.includes(port)) port = await freePort(); ports.push(port);
      const env = { ...process.env, PORT: String(port), HOST: "127.0.0.1" };
      const argsFor = (cmd: string[]) => cmd.map(arg => arg.replaceAll("{port}", String(port)));
      for (const stage of ["install", "build"] as const) {
        const command = config[stage]; if (!command) continue;
        const args = argsFor(command); const start = performance.now();
        const run = spawnSync(args[0]!, args.slice(1), { cwd: worktree, env, encoding: "utf8", timeout: config.buildTimeoutMs, maxBuffer: 16*1024*1024 });
        await writeFile(resolve(out, `${side}-${stage}.log`), (run.stdout ?? "") + (run.stderr ?? ""));
        timings[`${side}_${stage}_seconds`] = (performance.now() - start)/1000;
        if (run.error || run.status !== 0) throw new Error(`${side} ${stage} failed: ${run.error?.message ?? run.status}; see ${out}`);
      }
      const args = argsFor(config.start);
      const server = spawn(args[0]!, args.slice(1), { cwd: worktree, env, detached: process.platform !== "win32", stdio: ["ignore", "pipe", "pipe"] });
      servers.push(server);
      const log = createWriteStream(resolve(out, `${side}-server.log`));
      server.stdout!.pipe(log, { end: false }); server.stderr!.pipe(log, { end: false });
      server.once("close", () => log.end());
      let launchError: Error | undefined; server.once("error", error => { launchError = error; });
      const deadline = Date.now() + config.startupTimeoutMs; let ready = false;
      while (Date.now() < deadline) {
        if (launchError || server.exitCode !== null || server.signalCode !== null) throw launchError ?? new Error(`${side} server exited; see ${out}`);
        try { ready = (await fetch(`http://127.0.0.1:${port}${config.readyPath}`, { signal: AbortSignal.timeout(1000) })).ok; } catch { /* retry until ready */ }
        if (ready) break;
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      if (!ready) throw new Error(`${side} server did not become ready`);
    }
    // All installation/build work finishes before any measurements start.
    await compare(["--url", `http://127.0.0.1:${ports[0]}${config.path}`, "--pr-url", `http://127.0.0.1:${ports[1]}${config.path}`,
      "--runs", values.runs!, "--app", config.app, "--label", refs[0] === refs[1] ? "aa" : "commit",
      "--app-build", `${refs[0]}..${refs[1]}`, "--out", resolve(out, "comparison")]);
  } finally {
    for (const server of servers) {
      if (server.pid) {
        try {
          if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"]);
          else process.kill(-server.pid, "SIGTERM");
        } catch { /* already stopped */ }
      }
    }
    await Promise.all(servers.filter(s => s.exitCode === null && s.signalCode === null).map(s => new Promise<void>(done => {
      const timer = setTimeout(() => { try { if (s.pid && process.platform !== "win32") process.kill(-s.pid, "SIGKILL"); } catch {} done(); }, 2000);
      s.once("close", () => { clearTimeout(timer); done(); });
    })));
    const cleanupIssues: string[] = [];
    for (const worktree of worktrees.reverse()) {
      try { git(["worktree", "remove", "--force", worktree]); } catch (error) { cleanupIssues.push(String(error)); }
    }
    if (!cleanupIssues.length) await rm(temp, { recursive: true, force: true });
    await writeFile(resolve(out, "refs.json"), JSON.stringify({ repo, base: refs[0], pr: refs[1], config,
      timings, total_seconds: (performance.now()-started)/1000, cleanup_issues: cleanupIssues }, null, 2)+"\n");
    if (cleanupIssues.length) throw new Error(`worktree cleanup failed; inspect ${out}/refs.json`);
  }
}

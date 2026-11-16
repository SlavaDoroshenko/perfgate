/** Seeded on/off CPU load beside a measurement, standing in for neighbouring CI jobs.
 *
 * Exploratory instrument of docs/protocols/extensions-2026-11-17.md, outside the frozen
 * collector. Busy-loops `--workers` threads during "on" periods; on and off periods are
 * drawn uniformly from [--min-s, --max-s] by a seeded generator, so a schedule can be
 * reproduced from its seed. Every switch is appended to `--log` as JSON lines.
 * Runs until killed (SIGTERM/SIGINT), or for `--duration-s` if given.
 */
import { Worker, isMainThread, workerData, parentPort } from "node:worker_threads";
import { appendFileSync } from "node:fs";
import { availableParallelism } from "node:os";
import { parseArgs } from "node:util";

if (!isMainThread) {
  const flag = new Int32Array(workerData);
  // spin while the shared flag is 1, sleep on it while 0
  for (;;) {
    if (Atomics.load(flag, 0) === 1) {
      let x = 0;
      for (let i = 0; i < 1e6; i++) x += Math.sqrt(i);
      if (x < 0) parentPort.postMessage(x);
    } else {
      Atomics.wait(flag, 0, 0, 1000);
    }
  }
}

const { values } = parseArgs({ options: {
  seed: { type: "string" }, workers: { type: "string", default: "2" },
  "min-s": { type: "string", default: "5" }, "max-s": { type: "string", default: "60" },
  "duration-s": { type: "string" }, log: { type: "string" },
} });
const seed = Number(values.seed), workers = Number(values.workers);
const minS = Number(values["min-s"]), maxS = Number(values["max-s"]);
if (!Number.isSafeInteger(seed) || !Number.isInteger(workers) || workers < 1 ||
    !(minS > 0) || !(maxS >= minS) || !values.log) {
  throw new Error("Required: --seed INT --log FILE; positive --workers, 0 < --min-s <= --max-s");
}

// mulberry32: small, explicit and reproducible across Node versions
let state = seed >>> 0;
const random = () => {
  state = (state + 0x6d2b79f5) >>> 0;
  let t = state;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const log = (event) => appendFileSync(values.log, JSON.stringify({ t: new Date().toISOString(), ...event }) + "\n");

const shared = new SharedArrayBuffer(4);
const flag = new Int32Array(shared);
const threads = Array.from({ length: workers }, () => new Worker(new URL(import.meta.url), { workerData: shared }));
log({ event: "start", seed, workers, cpus: availableParallelism(), min_s: minS, max_s: maxS });

let on = random() < 0.5;
let timer;
const step = () => {
  Atomics.store(flag, 0, on ? 1 : 0);
  Atomics.notify(flag, 0);
  const seconds = minS + (maxS - minS) * random();
  log({ event: on ? "on" : "off", seconds });
  on = !on;
  timer = setTimeout(step, seconds * 1000);
};
const stop = () => {
  clearTimeout(timer);
  log({ event: "stop" });
  for (const thread of threads) thread.terminate();
};
process.on("SIGTERM", stop);
process.on("SIGINT", stop);
if (values["duration-s"]) setTimeout(stop, Number(values["duration-s"]) * 1000);
step();

#!/usr/bin/env node
// Builds one case from oss/cases.json twice — at the "before" ref and at the "after" ref —
// and copies both dist trees into one served directory. This is somebody else's code,
// somebody else's install and somebody else's build, so it is expected to be the most
// fragile part of the bench: failures are reported per side, not swallowed.
import { execFileSync } from "node:child_process";
import { cp, mkdir, readFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { parseArgs } from "node:util";
import { resolve } from "node:path";

const { values } = parseArgs({
  options: {
    case: { type: "string" },
    work: { type: "string", default: ".oss-work" },
    out: { type: "string", default: ".oss-dist" },
    list: { type: "boolean", default: false },
  },
});

const root = resolve(import.meta.dirname, "..");
const cases = JSON.parse(await readFile(resolve(root, "oss/cases.json"), "utf8"));

if (values.list) {
  for (const c of cases) console.log(c.id);
  process.exit(0);
}

const testCase = cases.find((c) => c.id === values.case);
if (!testCase) {
  console.error(`unknown case "${values.case}"; known: ${cases.map((c) => c.id).join(", ")}`);
  process.exit(2);
}

const run = (cmd, cwd) => {
  process.stderr.write(`$ ${cmd}\n`);
  execFileSync(cmd, { cwd, shell: true, stdio: "inherit", env: { ...process.env, CI: "1" } });
};

for (const side of ["before", "after"]) {
  const ref = testCase[side];
  const dir = resolve(root, values.work, testCase.id, side);
  const dest = resolve(root, values.out, testCase.id, side);

  if (!existsSync(dir)) {
    await mkdir(dir, { recursive: true });
    // full history is not needed, but the ref must be reachable
    run(`git clone --filter=blob:none ${testCase.repo} .`, dir);
  }
  run(`git checkout --detach ${ref}`, dir);
  run(testCase.install, dir);
  run(testCase.build, dir);

  await rm(dest, { recursive: true, force: true });
  await mkdir(dest, { recursive: true });
  await cp(resolve(dir, testCase.dist), dest, { recursive: true });
  process.stderr.write(`built ${testCase.id}/${side} (${ref})\n`);
}

process.stdout.write(`${testCase.id}: before=${testCase.before} after=${testCase.after}\n`);

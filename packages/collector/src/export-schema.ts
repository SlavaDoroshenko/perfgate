import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { z } from "zod";

import { Run } from "./schema.js";

const target = fileURLToPath(new URL("../../../schema/run.schema.json", import.meta.url));
await mkdir(dirname(target), { recursive: true });
await writeFile(target, JSON.stringify(z.toJSONSchema(Run), null, 2) + "\n");
process.stderr.write(`wrote ${target}\n`);

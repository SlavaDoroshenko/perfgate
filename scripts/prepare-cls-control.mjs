/** Create a separate diagnostic page without changing the historical workload. */
import { readFile, writeFile } from "node:fs/promises";
const original = new URL("../apps/demo-spa/dist/heavy.html", import.meta.url);
const html = await readFile(original, "utf8");
if (!html.includes("</head>")) throw new Error("Expected built heavy.html");
await writeFile(new URL("heavy-reserved.html", original), html.replace("</head>",
  '<style data-experiment="reserve-stats">.stats { height: 200px; overflow: hidden; }</style></head>'), { flag: "wx" });

import { DateTime } from "vendor:luxon";

import "./style.css";

// Serialising timestamps for an API or a table: luxon 2.3.0 lists "major perf improvements"
// to exactly these four methods.
const start = Date.UTC(2020, 0, 1);
const rows: string[] = [];
for (let i = 0; i < 6000; i++) {
  const d = DateTime.fromMillis(start + i * 3_600_000, { zone: "utc" });
  rows.push(`<tr><td>${d.toISO()}</td><td>${d.toISODate()}</td><td>${d.toISOTime()}</td><td>${d.toSQLDate()}</td></tr>`);
}
document.getElementById("out")!.innerHTML =
  `<table><tr><th>ISO</th><th>Date</th><th>Time</th><th>SQL</th></tr>${rows.slice(0, 400).join("")}</table>`;

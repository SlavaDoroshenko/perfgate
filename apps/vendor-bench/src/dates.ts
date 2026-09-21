import { addDays, format } from "vendor:dates";

import "./style.css";

const start = new Date(2020, 0, 1);
const rows: string[] = [];
for (let i = 0; i < 4000; i++) {
  const d = addDays(start, i);
  rows.push(
    `<tr><td>${format(d, "yyyy-MM-dd")}</td><td>${format(d, "EEEE")}</td>` +
      `<td>${format(d, "MMMM do, yyyy")}</td><td>${format(d, "QQQ")}</td></tr>`,
  );
}
document.getElementById("out")!.innerHTML =
  `<table><tr><th>ISO</th><th>Weekday</th><th>Long</th><th>Quarter</th></tr>${rows.slice(0, 400).join("")}</table>`;

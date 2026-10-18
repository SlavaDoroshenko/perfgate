import { parse } from "vendor:yaml";

import "./style.css";

// A configuration document that reuses shared blocks through anchors and aliases, like a
// CI or deployment config. yaml 2.8.0 added a node cache for alias resolution.
function document_(anchors: number, items: number): string {
  const lines: string[] = ["defaults:"];
  for (let a = 0; a < anchors; a++) {
    lines.push(`  base${a}: &b${a}`, `    region: r${a % 7}`, `    replicas: ${(a % 5) + 1}`, `    tier: t${a % 3}`);
  }
  lines.push("services:");
  for (let i = 0; i < items; i++) {
    lines.push(`  - name: service-${i}`, `    port: ${8000 + i}`, `    config: *b${i % anchors}`, `    extra: *b${(i * 7) % anchors}`);
  }
  return lines.join("\n");
}

type Service = { name: string; port: number; config: { region: string; replicas: number } };
// alias counting guards against "billion laughs" input; this document is trusted and large
const data = parse(document_(100, 500), { maxAliasCount: -1 }) as { services: Service[] };

const rows = data.services
  .slice(0, 400)
  .map((s) => `<tr><td>${s.name}</td><td>${s.port}</td><td>${s.config.region}</td><td>${s.config.replicas}</td></tr>`);
document.getElementById("out")!.innerHTML =
  `<p>${data.services.length} services</p><table><tr><th>Name</th><th>Port</th><th>Region</th><th>Replicas</th></tr>${rows.join("")}</table>`;

import { marked } from "vendor:marked";

import "./style.css";

/** Deterministic markdown document, large enough that parsing is real work. */
function document_(sections: number): string {
  const parts: string[] = ["# Release notes\n"];
  for (let i = 0; i < sections; i++) {
    parts.push(`## Section ${i}\n`);
    parts.push(`Paragraph with **bold**, _italic_ and \`code\` in it, number ${i}.\n`);
    parts.push("- first item\n- second item\n- third item\n");
    parts.push("| column | value |\n|---|---|\n| left | right |\n");
    parts.push("```js\nconst answer = " + i + ";\n```\n");
    parts.push("> A quotation that adds another block type.\n");
  }
  return parts.join("\n");
}

const html = marked.parse(document_(300));
const out = document.getElementById("out")!;
if (typeof html === "string") out.innerHTML = html;
else void html.then((v) => (out.innerHTML = v));

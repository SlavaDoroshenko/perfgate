import DOMPurify from "vendor:purify";

import "./style.css";

// Sanitising user-generated HTML before inserting it: a mix of allowed markup, event
// handlers, script urls and SVG, as comments or rich text would contain.
function untrusted(blocks: number): string {
  const parts: string[] = [];
  for (let i = 0; i < blocks; i++) {
    parts.push(
      `<div class="c${i % 7}"><p onclick="alert(${i})">Comment ${i} with <b>bold</b>, <i>italic</i> ` +
        `and <a href="javascript:alert(${i})">a bad link</a> and <a href="https://example.org/${i}">a good one</a>.</p>` +
        `<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" onerror="alert(${i})" alt="image ${i}">` +
        `<ul><li>one</li><li>two <span style="color:red">${i}</span></li></ul>` +
        `<svg width="10" height="10"><circle r="${i % 9}"></circle><script>alert(${i})</script></svg>` +
        `<blockquote><div><section><p>nested ${i}</p></section></div></blockquote></div>`,
    );
  }
  return parts.join("");
}

const dirty = untrusted(1500);

const clean = DOMPurify.sanitize(dirty) as string;
document.getElementById("out")!.innerHTML = clean;

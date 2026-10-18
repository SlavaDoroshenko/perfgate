import { createApp } from "vendor:vue-compile";

import "./style.css";

// A large in-DOM style template compiled in the browser: the page pays for Vue's template
// parser at load time, which is the part rewritten in 3.4.
function template(blocks: number): string {
  const parts: string[] = ['<div class="list">'];
  for (let i = 0; i < blocks; i++) {
    parts.push(
      `<section class="card" :class="{ odd: count % 2 === ${i % 2} }" data-index="${i}">` +
        `<h2 :title="title + ' ${i}'">{{ title }} ${i}</h2>` +
        `<p v-if="show">Paragraph <strong>{{ count + ${i} }}</strong> with <em>static</em> and ` +
        `<a href="#s${i}">a link</a>.</p><p v-else>hidden</p>` +
        `<ul><li v-for="t in tags" :key="t">{{ t }} / ${i}</li></ul>` +
        `<button type="button" @click="count++">+1</button>` +
        `</section>`,
    );
  }
  parts.push("</div>");
  return parts.join("");
}

createApp({
  template: template(1500),
  data: () => ({ title: "Section", count: 0, show: true, tags: ["a", "b", "c"] }),
}).mount("#app");

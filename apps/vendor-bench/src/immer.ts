import { produce } from "vendor:immer";

import "./style.css";

// A reducer-style sequence of immutable updates, each of which also reads the whole list
// through array methods: the access pattern Immer 10.2-11.x was optimised for.
type Item = { id: number; title: string; done: boolean; meta: { views: number } };
type State = { items: Item[]; log: string[] };

let state: State = {
  items: Array.from({ length: 2000 }, (_, i) => ({ id: i, title: `Item ${i}`, done: i % 3 === 0, meta: { views: 0 } })),
  log: [],
};

for (let step = 0; step < 120; step++) {
  state = produce(state, (d: State) => {
    const item = d.items[(step * 37) % d.items.length];
    item.done = !item.done;
    item.meta.views += 1;
    const doneCount = d.items.filter((x) => x.done).length;
    if (step % 10 === 0) d.items.push({ id: 2000 + step, title: `New ${step}`, done: false, meta: { views: 0 } });
    if (step % 30 === 0) d.items = d.items.filter((x) => x.id % 97 !== step % 97);
    d.log.push(`step ${step}: ${doneCount} done`);
  });
}

const rows = state.items
  .slice(0, 400)
  .map((x) => `<tr><td>${x.id}</td><td>${x.title}</td><td>${x.done ? "done" : "open"}</td><td>${x.meta.views}</td></tr>`);
document.getElementById("out")!.innerHTML =
  `<p>${state.items.length} items, ${state.log.length} updates; last: ${state.log[state.log.length - 1]}</p>` +
  `<table><tr><th>ID</th><th>Title</th><th>State</th><th>Views</th></tr>${rows.join("")}</table>`;

import { computed, createApp, h, reactive } from "vendor:vue-reactive";

import "./style.css";

// A large, deeply reactive array read through array methods: the case the 3.5 reactivity
// refactor targets. Computed values are re-read after each edit, as a dashboard would.
type Row = { id: number; value: number; done: boolean; tags: number[] };
const state = reactive({
  rows: Array.from({ length: 20000 }, (_, i): Row => ({
    id: i,
    value: (i * 7919) % 1000,
    done: i % 4 === 0,
    tags: [i % 3, i % 5],
  })),
});

const total = computed(() => state.rows.reduce((s: number, r: Row) => s + r.value, 0));
const open = computed(() => state.rows.filter((r: Row) => !r.done).length);
const top = computed(() => state.rows.slice().sort((a: Row, b: Row) => b.value - a.value || a.id - b.id).slice(0, 200));

let checksum = 0;
for (let k = 0; k < 30; k++) {
  state.rows[(k * 37) % state.rows.length].value += 1;
  if (k % 3 === 0) state.rows.push({ id: 20000 + k, value: k, done: false, tags: [k] });
  checksum += total.value + open.value;
}

createApp({
  render: () =>
    h("div", { id: "out" }, [
      h("p", `total ${total.value}, open ${open.value}, checksum ${checksum}`),
      h(
        "table",
        top.value.map((r: Row) =>
          h("tr", { key: r.id }, [h("td", String(r.id)), h("td", String(r.value)), h("td", r.done ? "done" : "open")]),
        ),
      ),
    ]),
}).mount("#app");

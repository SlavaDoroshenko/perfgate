import { z } from "vendor:zod";

import "./style.css";

// Validation of an API response on the client: a typical schema, a few thousand records.
const User = z.object({
  id: z.number().int().nonnegative(),
  name: z.string().min(1).max(64),
  email: z.string().email(),
  tags: z.array(z.string().max(16)).max(8),
  address: z.object({ city: z.string(), zip: z.string().regex(/^\d{5}$/) }),
  active: z.boolean(),
  score: z.number().min(0).max(100).optional(),
});
const Payload = z.array(User);

// deterministic records, no randomness between loads
const records = Array.from({ length: 4000 }, (_, i) => ({
  id: i,
  name: `User ${i}`,
  email: `user${i}@example.org`,
  tags: ["alpha", "beta", "gamma", "delta"].slice(0, (i % 4) + 1),
  address: { city: `City ${i % 50}`, zip: String(10000 + (i % 89999)) },
  active: i % 3 !== 0,
  score: i % 5 === 0 ? undefined : i % 101,
}));

let users: Array<{ id: number; name: string; email: string; active: boolean }> = [];
// the same payload validated several times, as a page re-fetching it would
for (let round = 0; round < 5; round++) users = Payload.parse(records);

const rows = users
  .slice(0, 400)
  .map((u) => `<tr><td>${u.id}</td><td>${u.name}</td><td>${u.email}</td><td>${u.active ? "yes" : "no"}</td></tr>`);
document.getElementById("out")!.innerHTML =
  `<p>${users.length} records valid</p><table><tr><th>ID</th><th>Name</th><th>Email</th><th>Active</th></tr>${rows.join("")}</table>`;

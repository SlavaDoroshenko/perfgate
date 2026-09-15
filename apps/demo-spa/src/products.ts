export interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  color: string;
}

const ADJECTIVES = ["Classic", "Light", "Warm", "Compact", "Soft", "Bold", "Urban", "Quiet"];
const NOUNS = ["Jacket", "Backpack", "Lamp", "Mug", "Scarf", "Chair", "Kettle", "Notebook"];

// Deterministic catalog: identical DOM on every load keeps the page itself noise-free.
export const products: Product[] = Array.from({ length: 60 }, (_, i) => ({
  id: i,
  name: `${ADJECTIVES[i % ADJECTIVES.length]} ${NOUNS[(i * 3) % NOUNS.length]}`,
  description: "Carefully made, ships in two days. Free returns within a month.",
  price: 9.99 + ((i * 37) % 200),
  color: `hsl(${(i * 47) % 360} 45% 70%)`,
}));

import { useEffect, useState } from "react";

import type { Inject } from "./inject";
import { products } from "./products";

export function App({ inject }: { inject: Inject | null }) {
  const lcpDelay = inject?.type === "lcp-delay" ? inject.size : 0;
  const [heroSrc, setHeroSrc] = useState(lcpDelay ? undefined : "/hero.svg");
  const [banner, setBanner] = useState(false);

  useEffect(() => {
    if (!lcpDelay) return;
    const t = setTimeout(() => setHeroSrc("/hero.svg"), lcpDelay);
    return () => clearTimeout(t);
  }, [lcpDelay]);

  useEffect(() => {
    if (inject?.type !== "layout-shift") return;
    const t = setTimeout(() => setBanner(true), 300);
    return () => clearTimeout(t);
  }, [inject]);

  return (
    <>
      {banner && (
        <div className="banner" style={{ height: inject!.size }}>
          Free delivery on orders over 50
        </div>
      )}
      <header className="header">
        <strong>Demo shop</strong>
        <nav>
          <a href="#">Catalog</a>
          <a href="#">Deals</a>
          <a href="#">Cart</a>
        </nav>
      </header>
      <main>
        <img className="hero" src={heroSrc} width={1200} height={480} alt="Autumn sale" />
        <h1>Popular right now</h1>
        <ul className="grid">
          {products.map((p) => (
            <li key={p.id} className="card">
              <div className="thumb" style={{ background: p.color }} />
              <h2>{p.name}</h2>
              <p>{p.description}</p>
              <span className="price">{p.price.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}

import { useEffect, useState } from "react";

import type { Inject } from "./inject";
import { makeProducts } from "./products";
import { buildSeries, sparkline, summarize, type Summary } from "./work";

// A page with the main-thread cost of a real app: large DOM, post-paint computation
// in several chunks (non-zero TBT) and a late banner (non-zero CLS).
const PRODUCTS = makeProducts(400);
// TBT only counts the part of a task above 50 ms, so each chunk must be clearly
// longer than that even on a fast machine — otherwise TBT stays a degenerate zero.
const CHUNKS = 3;
const SERIES_LENGTH = 400_000;

export function HeavyApp({ inject }: { inject: Inject | null }) {
  const lcpDelay = inject?.type === "lcp-delay" ? inject.size : 0;
  const [heroSrc, setHeroSrc] = useState(lcpDelay ? undefined : "/hero.svg");
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [path, setPath] = useState("");
  const [promo, setPromo] = useState(false);
  const shiftPx = inject?.type === "layout-shift" ? inject.size : 64;

  useEffect(() => {
    if (!lcpDelay) return;
    const t = setTimeout(() => setHeroSrc("/hero.svg"), lcpDelay);
    return () => clearTimeout(t);
  }, [lcpDelay]);

  useEffect(() => {
    // deterministic work after the first frame, split into chunks like a real dashboard
    const timers = Array.from({ length: CHUNKS }, (_, chunk) =>
      setTimeout(() => {
        const series = buildSeries(SERIES_LENGTH, 42 + chunk);
        const summary = summarize(series);
        setSummaries((prev) => [...prev, summary]);
        if (chunk === 0) setPath(sparkline(series, 600, 120));
      }, chunk * 16),
    );
    // late promo banner: the layout shift every real shop has
    timers.push(setTimeout(() => setPromo(true), 300));
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <>
      {promo && (
        <div className="banner" style={{ height: shiftPx }}>
          Autumn sale: up to 40% off
        </div>
      )}
      <header className="header">
        <strong>Demo shop — analytics</strong>
        <nav>
          <a href="#">Overview</a>
          <a href="#">Catalog</a>
          <a href="#">Reports</a>
        </nav>
      </header>
      <main>
        <img className="hero" src={heroSrc} width={1200} height={480} alt="Autumn sale" />
        <h1>Sales overview</h1>
        <svg className="chart" viewBox="0 0 600 120" width="600" height="120" role="img" aria-label="Sales trend">
          <path d={path} fill="none" stroke="#1e3a5f" strokeWidth="2" />
        </svg>
        <ul className="stats">
          {summaries.map((s, i) => (
            <li key={i}>
              <span className="stat-label">Segment {i + 1}</span>
              <span className="stat-value">{s.mean.toFixed(2)}</span>
              <span className="stat-sub">p95 {s.p95.toFixed(1)} · max {s.max.toFixed(1)}</span>
            </li>
          ))}
        </ul>
        <h2>Catalog</h2>
        <ul className="grid">
          {PRODUCTS.map((p) => (
            <li key={p.id} className="card">
              <div className="thumb" style={{ background: p.color }} />
              <h3>{p.name}</h3>
              <p>{p.description}</p>
              <span className="price">{p.price.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}

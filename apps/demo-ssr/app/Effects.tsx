"use client";

import { useEffect, useState } from "react";

import type { Inject } from "./inject";

/** Client-side half of the injected regressions, identical in semantics to the SPA demo. */
export function Effects({ inject }: { inject: Inject | null }) {
  const [banner, setBanner] = useState(false);
  const shiftPx = inject?.type === "layout-shift" ? inject.size : 64;

  useEffect(() => {
    if (inject?.type === "long-task") {
      const size = inject.size;
      requestAnimationFrame(() =>
        setTimeout(() => {
          const end = performance.now() + size;
          while (performance.now() < end) {
            // blocking the main thread on purpose
          }
        }, 0),
      );
    }
    const t = setTimeout(() => setBanner(true), 300);
    return () => clearTimeout(t);
  }, [inject]);

  if (!banner) return null;
  return (
    <div className="banner" style={{ height: shiftPx }}>
      Free delivery on orders over 50
    </div>
  );
}

/** Hero image whose src is assigned late when lcp-delay is injected. */
export function Hero({ delay }: { delay: number }) {
  const [src, setSrc] = useState<string | undefined>(delay ? undefined : "/hero.svg");
  useEffect(() => {
    if (!delay) return;
    const t = setTimeout(() => setSrc("/hero.svg"), delay);
    return () => clearTimeout(t);
  }, [delay]);
  return <img className="hero" src={src} width={1200} height={480} alt="Autumn sale" />;
}

import { Effects, Hero } from "./Effects";
import { parseInject } from "./inject";
import { makeProducts } from "./products";

// Rendered per request, never cached, so every measured load does the same server work.
export const dynamic = "force-dynamic";

const PRODUCTS = makeProducts(120);

export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const inject = parseInject((await searchParams).inject);
  const lcpDelay = inject?.type === "lcp-delay" ? inject.size : 0;

  return (
    <>
      {/* script-delay: a blocking script in the document, before the content is parsed */}
      {inject?.type === "script-delay" && (
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var e=performance.now()+${inject.size};while(performance.now()<e){}})();`,
          }}
        />
      )}
      <Effects inject={inject} />
      <header className="header">
        <strong>Demo shop</strong>
        <nav>
          <a href="#">Catalog</a>
          <a href="#">Deals</a>
          <a href="#">Cart</a>
        </nav>
      </header>
      <main>
        <Hero delay={lcpDelay} />
        <h1>Popular right now</h1>
        <ul className="grid">
          {PRODUCTS.map((p) => (
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

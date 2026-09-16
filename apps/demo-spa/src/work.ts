// Deterministic CPU work, so the heavy page has the main-thread cost of a real
// app (non-zero TBT) without any randomness of its own.

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function buildSeries(n: number, seed = 42): Float64Array {
  const rnd = mulberry32(seed);
  const out = new Float64Array(n);
  let value = 100;
  for (let i = 0; i < n; i++) {
    value += (rnd() - 0.5) * 4;
    out[i] = value;
  }
  return out;
}

export interface Summary {
  mean: number;
  p95: number;
  max: number;
  buckets: number[];
}

export function summarize(series: Float64Array, buckets = 40): Summary {
  const sorted = Float64Array.prototype.slice.call(series).sort();
  const min = sorted[0]!;
  const max = sorted[sorted.length - 1]!;
  const width = (max - min) / buckets || 1;
  const hist = new Array<number>(buckets).fill(0);
  let sum = 0;
  for (let i = 0; i < series.length; i++) {
    const v = series[i]!;
    sum += v;
    const b = Math.min(buckets - 1, Math.floor((v - min) / width));
    hist[b] = hist[b]! + 1;
  }
  return {
    mean: sum / series.length,
    p95: sorted[Math.floor(sorted.length * 0.95)]!,
    max,
    buckets: hist,
  };
}

/** Sparkline path over a downsampled series. */
export function sparkline(series: Float64Array, width: number, height: number, points = 120): string {
  const step = Math.max(1, Math.floor(series.length / points));
  const sampled: number[] = [];
  for (let i = 0; i < series.length; i += step) sampled.push(series[i]!);
  const min = Math.min(...sampled);
  const max = Math.max(...sampled);
  const span = max - min || 1;
  return sampled
    .map((v, i) => {
      const x = (i / (sampled.length - 1)) * width;
      const y = height - ((v - min) / span) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

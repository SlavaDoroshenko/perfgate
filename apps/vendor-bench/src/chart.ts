import { Chart, registerables } from "vendor:chart";

import "./style.css";

Chart.register(...(registerables as never[]));

// deterministic series, no randomness between loads
const points = Array.from({ length: 2000 }, (_, i) => 50 + 40 * Math.sin(i / 25) + (i % 17));
const canvas = document.getElementById("chart") as HTMLCanvasElement;

new Chart(canvas, {
  type: "line",
  data: {
    labels: points.map((_, i) => String(i)),
    datasets: [
      { label: "latency", data: points, borderColor: "#1e3a5f", pointRadius: 0, borderWidth: 1 },
      { label: "throughput", data: points.map((v) => 120 - v), borderColor: "#4f9d8f", pointRadius: 0, borderWidth: 1 },
    ],
  },
  options: { animation: false, responsive: false, scales: { x: { ticks: { maxTicksLimit: 12 } } } },
});

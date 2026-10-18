// Browsertime script: one page load of $PERFGATE_URL with the network throttling Lighthouse
// applies in `devtools` mode (mobileSlow4G, request-level via CDP). CPU throttling (4x) and the
// Moto G Power viewport are set on the command line; browsertime has no request-level network
// throttling of its own, and its `throttle` engine only adds latency on localhost.
//
// Values: lighthouse/core/config/constants.js + core/lib/emulation.js (Lighthouse 13.4.1).
const LATENCY_MS = 562.5; // 150 ms RTT × 3.75
const DOWNLOAD_BYTES_PER_S = Math.floor((1474.56 * 1024) / 8); // 1.6 Mbps × 0.9
const UPLOAD_BYTES_PER_S = Math.floor((675 * 1024) / 8); // 750 kbps × 0.9

export default async function (context, commands) {
  const url = process.env.PERFGATE_URL;
  if (!url) throw new Error("PERFGATE_URL is not set");
  await commands.cdp.send("Network.enable", {});
  await commands.cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: LATENCY_MS,
    downloadThroughput: DOWNLOAD_BYTES_PER_S,
    uploadThroughput: UPLOAD_BYTES_PER_S,
  });
  return commands.measure.start(url);
}

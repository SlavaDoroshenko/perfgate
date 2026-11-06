// A separate diagnostic workload; historical demo sources are unchanged.
(() => {
  const query = new URLSearchParams(location.search);
  const active = query.get('stall') === '1';
  const duration = Number(query.get('stall_ms'));
  if (!Number.isFinite(duration) || duration < 0 || duration > 5000) throw new Error('Invalid stall duration');
  performance.mark('perfgate-tail-ready');
  addEventListener('load', () => {
    requestAnimationFrame(() => setTimeout(() => {
      if (active) {
        performance.mark('perfgate-stall-start');
        const end = performance.now() + duration;
        while (performance.now() < end) { /* intentional wall-clock main-thread stall */ }
        performance.mark('perfgate-stall-end');
      }
      performance.mark('perfgate-tail-done');
    }, 0));
  }, { once: true });
})();

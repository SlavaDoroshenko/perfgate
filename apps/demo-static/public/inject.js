// Same four injected regressions as the other demo apps, driven by ?inject=type:size.
(function () {
  var raw = new URLSearchParams(location.search).get('inject') || '';
  var parts = raw.split(':');
  var type = parts[0];
  var size = Number(parts[1] || 0);
  if (raw && (!type || !isFinite(size) || size < 0)) throw new Error('bad inject param "' + raw + '"');

  function busyWait(ms) {
    var end = performance.now() + ms;
    while (performance.now() < end) {}
  }

  // long-task: blocking work right after the first frame
  if (type === 'long-task') {
    requestAnimationFrame(function () { setTimeout(function () { busyWait(size); }, 0); });
  }

  // layout-shift: a promo banner pushed above the content, like a late ad slot
  setTimeout(function () {
    var banner = document.createElement('div');
    banner.className = 'banner';
    banner.style.height = (type === 'layout-shift' ? size : 64) + 'px';
    banner.textContent = 'Subscribe to the weekly digest';
    document.body.insertBefore(banner, document.body.firstChild);
  }, 300);
})();

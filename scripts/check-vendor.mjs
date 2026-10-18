// Run after vendor-bench build + preview. Check both releases before measuring them:
// a blank page, runtime exception or missing asset is not a performance result.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const collector = createRequire(new URL('../packages/collector/package.json', import.meta.url));
const { launch } = collector('chrome-launcher');
const { default: puppeteer } = createRequire(collector.resolve('lighthouse'))('puppeteer-core');
const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu'] });
const browser = await puppeteer.connect({ browserURL: `http://127.0.0.1:${chrome.port}` });
const cases = ['marked', 'chart', 'dates', 'zod', 'vue-compile', 'vue-reactive', 'immer', 'yaml', 'luxon', 'jquery', 'purify'];
const origin = process.env.VENDOR_URL ?? 'http://127.0.0.1:4176';
try {
  for (const name of cases) {
    const outputs = [];
    for (const variant of ['a', 'b']) {
      const context = await browser.createBrowserContext();
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(String(error)));
      page.on('requestfailed', request => errors.push(`${request.url()}: ${request.failure()?.errorText}`));
      page.on('response', response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
      await page.goto(`${origin}/${variant}/${name}.html`, { waitUntil: 'networkidle0', timeout: 120000 });
      const output = await page.evaluate(() => ({
        text: (document.querySelector('#out') ?? document.querySelector('#app') ?? document.querySelector('main'))?.textContent?.trim(),
        canvas: !!document.querySelector('canvas'),
        images: [...document.images].every(img => img.complete && img.naturalWidth > 0),
      }));
      assert.deepEqual(errors, [], `${variant}/${name}: browser errors`);
      assert.ok(output.canvas || output.text?.length > 100, `${variant}/${name}: empty output`);
      assert.ok(output.images, `${variant}/${name}: broken image`);
      outputs.push(output.text);
      await context.close();
    }
    assert.equal(outputs[0], outputs[1], `${name}: releases render different text`);
    console.log(`${name}: both releases render equivalent content without errors`);
  }
} finally {
  await browser.disconnect();
  await chrome.kill();
}

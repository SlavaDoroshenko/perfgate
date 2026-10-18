// Preserve the actual compare-plugin verdict and samples, not a reimplementation.
import { writeFile } from 'node:fs/promises';

export default class Capture {
  getName() { return 'perfgate-capture'; }
  async open() {}
  async close() {}
  async processMessage(message) {
    if (message.type === 'compare.pageSummary') {
      await writeFile(process.env.PERFGATE_COMPARE_OUT, JSON.stringify(message.data, null, 2) + '\n');
    }
  }
}

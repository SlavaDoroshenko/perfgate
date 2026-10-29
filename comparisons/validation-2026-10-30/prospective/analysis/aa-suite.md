# perfgate: no_regression_detected

Policy: `browser-candidate-2026-10-30` (candidate).

| Metric | Base | PR | Change | 95% interval, absolute | Regression |
|---|---:|---:|---:|---:|---|
| demo-heavy/fcp (ms) | 1823 | 1822 | -0.5655; -0.03% | [-4.07, 7.352] | no |
| demo-heavy/lcp (ms) | 2315 | 2320 | +4.907; +0.21% | [-11, 11.96] | no |
| demo-heavy/tbt (ms) | 496.4 | 493.6 | -2.788; -0.56% | [-6.701, 3.542] | no |
| demo-heavy/cls (unitless) | 0.1545 | 0.1545 | +0; +0.00% | [0, 0] | no |
| demo-spa/fcp (ms) | 1692 | 1693 | +1.008; +0.06% | [-2.204, 3.032] | no |
| demo-spa/lcp (ms) | 2249 | 2249 | -0.372; -0.02% | [-3.442, 4.275] | no |
| demo-spa/tbt (ms) | 0 | 0 | +0; relative undefined (zero base) | [0, 0] | no |
| demo-spa/cls (unitless) | 0 | 0 | +0; relative undefined (zero base) | [0, 0] | no |
| demo-ssr/fcp (ms) | 1217 | 1214 | -3.551; -0.29% | [-7.045, 0.9919] | no |
| demo-ssr/lcp (ms) | 1217 | 1214 | -3.551; -0.29% | [-6.983, 1.329] | no |
| demo-ssr/tbt (ms) | 61.23 | 61.7 | +0.472; +0.77% | [-7.73, 7.624] | no |
| demo-ssr/cls (unitless) | 0.07776 | 0.07776 | +0; +0.00% | [0, 0] | no |
| demo-static/fcp (ms) | 1245 | 1248 | +2.082; +0.17% | [-2.302, 4.255] | no |
| demo-static/lcp (ms) | 1809 | 1810 | +0.6665; +0.04% | [-4.504, 5.421] | no |
| demo-static/tbt (ms) | 0 | 0 | +0; relative undefined (zero base) | [0, 0] | no |
| demo-static/cls (unitless) | 0.07776 | 0.07776 | +0; +0.00% | [0, 0] | no |

- Candidate policy; prospective validation is pending.
- No detected regression is not proof of equivalence.
- Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict.

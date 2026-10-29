# perfgate: no_regression_detected

Policy: `browser-candidate-2026-10-30` (candidate).

| Metric | Base | PR | Change | 95% interval, absolute | Regression |
|---|---:|---:|---:|---:|---|
| demo-heavy/fcp (ms) | 2555 | 2549 | -6.369; -0.25% | [-11.88, 5.746] | no |
| demo-heavy/lcp (ms) | 3106 | 3099 | -6.367; -0.21% | [-18.41, 5.672] | no |
| demo-heavy/tbt (ms) | 348.3 | 348.9 | +0.5595; +0.16% | [-8.947, 4.936] | no |
| demo-heavy/cls (unitless) | 0.2366 | 0.1572 | -0.07939; -33.55% | [-0.07939, 0] | no |

- Candidate policy; prospective validation is pending.
- No detected regression is not proof of equivalence.
- Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict.

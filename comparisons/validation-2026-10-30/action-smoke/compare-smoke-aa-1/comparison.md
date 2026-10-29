# perfgate: no_regression_detected

Policy: `browser-candidate-2026-10-30` (candidate).

| Metric | Base | PR | Change | 95% interval, absolute | Regression |
|---|---:|---:|---:|---:|---|
| demo-heavy/fcp (ms) | 1812 | 1811 | -0.2225; -0.01% | [-16.21, 13.71] | no |
| demo-heavy/lcp (ms) | 2333 | 2321 | -11.51; -0.49% | [-175.1, 171.7] | no |
| demo-heavy/tbt (ms) | 498.9 | 503 | +4.13; +0.83% | [-10.4, 16.67] | no |
| demo-heavy/cls (unitless) | 0.1545 | 0.1545 | +0; +0.00% | [0, 0] | no |

- Candidate policy; prospective validation is pending.
- No detected regression is not proof of equivalence.
- Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict.

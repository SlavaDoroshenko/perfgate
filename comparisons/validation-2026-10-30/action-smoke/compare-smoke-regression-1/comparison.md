# perfgate: regression

Policy: `browser-candidate-2026-10-30` (candidate).

| Metric | Base | PR | Change | 95% interval, absolute | Regression |
|---|---:|---:|---:|---:|---|
| demo-heavy/fcp (ms) | 1793 | 1970 | +177.1; +9.87% | [171.8, 183.9] | yes |
| demo-heavy/lcp (ms) | 2494 | 2470 | -24.87; -1.00% | [-36.63, 173.2] | no |
| demo-heavy/tbt (ms) | 487.4 | 488.7 | +1.286; +0.26% | [-7.11, 11.33] | no |
| demo-heavy/cls (unitless) | 0.1545 | 0.1545 | +0; +0.00% | [-0.03839, 0] | no |

- Candidate policy; prospective validation is pending.
- No detected regression is not proof of equivalence.
- Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict.

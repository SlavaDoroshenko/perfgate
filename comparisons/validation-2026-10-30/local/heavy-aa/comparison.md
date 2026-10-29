# perfgate: no_regression_detected

Policy: `browser-candidate-2026-10-30` (candidate).

| Metric | Base | PR | Change | 95% interval, absolute | Regression |
|---|---:|---:|---:|---:|---|
| demo-heavy/fcp (ms) | 2548 | 2548 | +0.2755; +0.01% | [-5.393, 9.867] | no |
| demo-heavy/lcp (ms) | 3107 | 3109 | +2.044; +0.07% | [-8.067, 16.82] | no |
| demo-heavy/tbt (ms) | 353.5 | 356.5 | +3; +0.85% | [-3.999, 8.534] | no |
| demo-heavy/cls (unitless) | 0.1572 | 0.1572 | +0; +0.00% | [-0.07939, 0.03969] | no |

- Candidate policy; prospective validation is pending.
- No detected regression is not proof of equivalence.
- Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict.

# perfgate: no_regression_detected

Policy: `browser-candidate-2026-10-30` (candidate).

| Metric | Base | PR | Change | 95% interval, absolute | Regression |
|---|---:|---:|---:|---:|---|
| demo-spa/fcp (ms) | 2485 | 2485 | +0.8195; +0.03% | [-4.305, 4.66] | no |
| demo-spa/lcp (ms) | 3032 | 3033 | +0.534; +0.02% | [-4.697, 6.045] | no |
| demo-spa/tbt (ms) | 0 | 0 | +0; relative undefined (zero base) | [0, 0] | no |
| demo-spa/cls (unitless) | 0 | 0 | +0; relative undefined (zero base) | [0, 0] | no |

- Candidate policy; prospective validation is pending.
- No detected regression is not proof of equivalence.
- Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict.

# perfgate: regression

Policy: `browser-candidate-2026-10-30` (candidate).

| Metric | Base | PR | Change | 95% interval, absolute | Regression |
|---|---:|---:|---:|---:|---|
| demo-heavy/fcp (ms) | 2544 | 2735 | +190.2; +7.48% | [183.5, 199.4] | yes |
| demo-heavy/lcp (ms) | 3102 | 3290 | +188; +6.06% | [175.9, 201] | yes |
| demo-heavy/tbt (ms) | 353.3 | 349.2 | -4.165; -1.18% | [-8.851, -0.1115] | no |
| demo-heavy/cls (unitless) | 0.1572 | 0.2366 | +0.07939; +50.49% | [-0.03969, 0.07939] | no |

- Candidate policy; prospective validation is pending.
- No detected regression is not proof of equivalence.
- Bootstrap intervals are pointwise and assume independent loads; they do not determine the verdict.

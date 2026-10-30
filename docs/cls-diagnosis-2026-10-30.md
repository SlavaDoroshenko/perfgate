# CLS calibration diagnosis, 30 October 2026

This is exploratory follow-up to the first frozen-policy pilot. It does not change
browser-candidate-2026-10-30 or turn the inspected pilot into a fresh holdout.

## What the recorded pilot actually shows

The earlier validation report describes the +25% case through its aggregate median
(+0.25% observed CLS). That number is correct, but "the injector failed" is not an
established causal explanation. Inspection of the full observations reveals two
very narrow modes in both variants, separated by the same 0.076782278741 units.

| Nominal case | Baseline low / high count | Treatment low / high count | Low-mode CLS, baseline → treatment |
|---|---:|---:|---|
| +2% | 20 / 0 | 20 / 0 | 0.154463 → 0.157558 |
| +5% | 11 / 9 | 14 / 6 | 0.154463 → 0.162228 |
| +10% | 16 / 4 | 19 / 1 | 0.154463 → 0.170012 |
| +25% | 10 / 10 | 15 / 5 | 0.154463 → 0.193345 |

In the +25% job, the even-sample baseline median averages the two modes:
(0.154462960715 + 0.231245239457) / 2 = 0.192854100086.
The treatment median is its lower mode, 0.193345099233. Their ratio gives +0.25%,
although the low mode increased +25.17% and the mean increased +10.21%.

Conditioning on modes is a diagnostic description, not a replacement endpoint or
permission to discard high-mode samples. Mode occupancy could depend on timing or
treatment. Neither this decomposition nor the aggregate mean establishes a causal
effect for an individual load. The frozen gate's missed target remains a missed
target under its predeclared rule.

## Trace follow-up

scripts/diagnose-cls.mjs captures complete Lighthouse traces, reports, per-event
layout shifts and affected DOM elements. It uses the same pinned Chrome, cold
browser launch, devtools throttling and alternating order as the collector, while
remaining an independent exploratory tool. Traces are diagnostic, not additional
confirmatory comparisons. Local and hosted findings must be distinguished.

CLS is the largest session-window sum of layout-shift scores; scores depend on
viewport movement, not simply banner height. See the primary
[CLS specification guide](https://web.dev/articles/cls).

## Controlled diagnostic design (declared before collection)

Two pages use the same built JavaScript and content. The original heavy.html is
unaltered. A separate heavy-reserved.html adds only a fixed 200 px stats container
with overflow clipped, preventing its asynchronous children from changing the
height occupied by that region. This is an intervention on the suspected confound,
not an optimized replacement for the historical benchmark.

For each page, capture four alternating base/treatment pairs after two warmups per
variant. Baseline banner is 64 px; treatment is 96 px. The reserved control has a
different CLS baseline, so its treatment is **not labelled nominal +25% CLS**.
Inspect all traces, including warmups; report measurement summaries separately.
The intervention is intended to test whether stats-region growth contributes to
the extra shifts and whether reserving that region isolates banner displacement.
A local experiment cannot establish exact Linux behavior; run both pages in a
manual hosted workflow with pinned Chrome before attributing the historical modes.
This small fixed diagnostic sample is not a statistical power experiment.

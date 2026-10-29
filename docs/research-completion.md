# Research completion contract

Updated 30 October 2026. A completed, reproducible empirical study is a required
project outcome before the thesis submission. A functioning CLI alone does not
satisfy this milestone. Negative results and clearly bounded applicability are
valid outcomes; the plan does not promise that every detector will succeed.

## Required evidence

| Question | Completion evidence | Current status |
|---|---|---|
| RQ1: noise and sensitivity | Validated corpus, per-configuration uncertainty and MDE at 5/10/20 loads; fixed versions/builds | Implemented; refreshed tables in progress |
| RQ2: detection rules | Common observations for all methods; A/A false alarms, injected power, measured effects, intervals and exclusion counts | Eleven historical rules plus exploratory permutation mean; whole-job validation added |
| RQ3: run order | Repeated real A/A comparisons, per-page and whole-check false alarms, fair sample counts | Repeated advantage of alternating order; final policy differs from historical RQ3 |
| Distribution shape | Explicit data-generating processes and null hypotheses; heavy tails, rare stalls and dependence; browser follow-up | Reproducible simulation implemented; browser tail experiment pending |
| Complete gate | Frozen metric family, margins, sample count and zero-baseline behavior; suite-level error rates | Candidate implemented, retrospective evaluation available |
| Prospective validation | Freeze before acquisition; untouched later data; disclose every policy change | Protocol below; future sample collection cannot be completed in one session |
| Resource budget | Warmup/measurement/analysis time, same-load and same-time comparisons separated | New measurements record durations; historical durations incomplete |
| External validity | Repeated OSS cases, additional local pages/sessions, actual sitespeed comparison with balanced tool order | OSS replicated; local/tool pilots need further expansion |
| History | Past-only training, later evaluation, overlap/dependence acknowledged; calibrate alert clusters/delay, not only window counts | Prototype and diagnostics; automatic blocking not justified |
| Reproducibility | Frozen data/source checksums, versioned protocols, scripts, tables, seeds, explicit exclusions | Available by stage; final release/archive pending |

## Candidate and prospective evaluation

Policy `browser-candidate-2026-10-30` uses the implementation and margins documented
in compare.md. It is evaluated retrospectively first. No inspected data, including
the 29 October snapshot, may be described as an untouched holdout.

Before collecting the confirmatory set, save a manifest of the exact candidate
source hashes and acquisition cutoff. Changes to hypotheses, margins, sample sizes
or exclusions create a new candidate and a new holdout. Warmups, versions, page
fingerprints and device/session descriptors must also be recorded.

Predeclared primary configuration: devtools, abab, two warmups, 20 loads/variant,
FCP/LCP/TBT/CLS, one-sided MWU with Holm over the whole requested page suite.
Ten-load comparisons are secondary; they are not an adaptive early-stop policy.

Engineering targets to test (not claims of achieved guarantees):

- At least 200 complete prospective four-page A/A suites, report invalid suites
  separately; target Wilson 95% upper false-alarm bound <=5%.
- At least 100 independent jobs per primary injected case; target Wilson 95% lower
  detection bound >=80% for changes materially above the candidate margins.
- Report nominal and measured size separately. Primary above-margin examples are
  FCP/LCP nominal 5%, TBT nominal 10%, CLS nominal 10/25%; any systematic failure
  to reach the intended effect is an injector limitation, not grounds to silently
  discard difficult jobs. Also report all smaller cases.
- Report target-metric detection and whole-check detection separately; a spurious
  unrelated metric must not be counted as correctly localizing the intended change.
- Publish point estimates and uncertainty even if a target is missed. Do not keep
  collecting until an interval happens to pass a target; use the fixed sample target.
- Review temporal dependence, runner changes and session effects. Wilson intervals
  assume independent trials and must be accompanied by sensitivity analysis when
  repeated runs cluster in time or by machine. Fixed sampling counts do not solve this.

These targets can be revised during exploration, but must be frozen with the
implementation before their confirmatory data are acquired. The first local MVP
checks are smoke tests and a new session pilot, not the confirmatory CI corpus.

## Scope and priority

1. Finish and test the shared quality contract and candidate comparison path.
2. Complete retrospective reports and diagnose weaknesses (including rare stalls).
3. Freeze the candidate and run prospective collection; in parallel finish URL/ref
   orchestration and GitHub integration.
4. Extend same-time tool comparisons, multiple local sessions and history calibration.
5. Assemble a reproducible release and a final limitations/claim matrix.

Do not make PELT or a large menu of additional tests substitutes for closing these
questions. Adding methods is useful only when it addresses an identified failure
mode. Native-platform support is a separate future scope (native-adapters.md).

## First distribution-shape result

The new `stress` module compares all eleven historical rules plus a permutation
mean test on identical simulated experiments, 500 repetitions at n=10 and n=20.
Cases include a location shift, lognormal heavy tails, rare stalls, a variance
change at constant population mean, and an AR(1) null with alternating/sequential
assignment. The variance-change case is a distribution change, not a shared null
for all the tests. Report its rejection rate without calling every rejection a
false positive. The permutation mean test assumes exchangeability under its null;
it does not cure serial dependence or arbitrary heteroscedasticity.

In the first n=20 simulation, adding a +100-unit stall with probability 15% is
detected by MWU+1% in 13.2%, Welch in 54.2%, and permutation mean in 45.8% of
experiments. A median gate is not a general tail-regression detector. This motivates
measured rare-task browser scenarios and an explicitly defined tail/mean endpoint,
not automatic replacement of the current policy based on one simulation.

Reproduce with `uv run --directory analysis python -m perfgate_analysis.stress
--out reports/stress --reps 500`. The additional method can also be included in
research refreshes with `--experimental-methods`; it is outside default_methods to
keep the historical eleven-rule comparison identifiable.

Reference for the added permutation test and its null hypothesis:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html

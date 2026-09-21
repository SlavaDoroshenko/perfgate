import numpy as np

from perfgate_analysis.evaluate import DELTAS, EvalConfig, evaluate, evaluate_real_jobs, summarize
from perfgate_analysis.load import to_frame
from perfgate_analysis.methods import mann_whitney, threshold

from .conftest import synthetic_records


def frame():
    return to_frame(synthetic_records(experiments=6, runs=20, sigma=0.03))


def test_evaluate_gives_every_method_the_same_draws():
    cfg = EvalConfig(reps=300)
    methods = [mann_whitney(), threshold(0.05)]
    rates = evaluate(frame(), methods=methods, metrics=("lcp",), sizes=(10,), cfg=cfg)
    assert set(rates["method"]) == {m.name for m in methods}
    assert len(rates) == len(DELTAS) * len(methods)
    # both must be calibrated at delta = 0 and certain at delta = 0.3
    zero = rates[rates.delta == 0].set_index("method")["rate"]
    big = rates[rates.delta == 0.3].set_index("method")["rate"]
    assert zero[mann_whitney().name] < 0.12
    assert (big > 0.95).all()


def test_summarize_reports_fpr_and_mde():
    rates = evaluate(frame(), methods=[mann_whitney()], metrics=("lcp",), sizes=(10,), cfg=EvalConfig(reps=300))
    s = summarize(rates)
    assert len(s) == 1
    assert 0 <= s["false_alarm_rate"].iloc[0] < 0.12
    assert 0 < s["mde"].iloc[0] <= 0.1


def test_real_jobs_split_aa_and_control():
    records = synthetic_records(experiments=2, runs=10, sigma=0.03)
    for r in records:
        if r["variant"] == "pr":
            r["inject"] = {"type": "script-delay", "size": 50}
            for k in ("fcp", "lcp", "si"):
                r["metrics"][k] *= 1.1
    df = to_frame(records)
    out = evaluate_real_jobs(df, methods=[mann_whitney()], metrics=("lcp",))
    assert set(out["kind"]) == {"control"}
    assert out["flagged"].all()
    assert np.isclose(out["effect"].median(), 0.1, atol=0.03)

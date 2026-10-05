from perfgate_analysis.load import to_frame
from perfgate_analysis.methods import mann_whitney
from perfgate_analysis.power import aa_jobs_like, cls_absolute, injected_jobs, job_verdicts, power_table, TARGET

from .conftest import synthetic_records


def bench(shift: float, size: float = 90.0):
    records = synthetic_records(experiments=4, runs=20, sigma=0.02, seed=7)
    for r in records:
        r["app"] = "demo-heavy"
        r["label"] = "injected"
        r["warmup"] = 2
        if r["variant"] == "pr":
            r["inject"] = {"type": "script-delay", "size": size}
            r["metrics"] = {**r["metrics"], "fcp": r["metrics"]["fcp"] * (1 + shift)}
    aa = synthetic_records(experiments=3, runs=20, sigma=0.02, seed=8)
    for r in aa:
        r["app"] = "demo-heavy"
        r["experimentId"] = "aa-" + r["experimentId"]
        r["label"] = "aa"
    return to_frame(records + aa)


def test_injected_jobs_keep_only_the_current_calibration():
    assert set(injected_jobs(bench(0.05))["pct"]) == {5}
    # a size the bench no longer uses is dropped
    assert injected_jobs(bench(0.05, size=50.0)).empty


def test_power_counts_jobs_flagged_on_the_target_metric():
    df = bench(0.05)
    jobs = injected_jobs(df)
    verdicts = job_verdicts(jobs, [mann_whitney()], TARGET, sizes=(10, 20), by=("kind", "pct"))
    assert set(verdicts["metric"]) == {"fcp"}
    power = power_table(verdicts)
    assert (power["power"] == 1.0).all()
    assert power["effect_median"].between(0.03, 0.07).all()
    aa = aa_jobs_like(df, jobs)
    assert aa["experiment"].nunique() == 3
    fpr = job_verdicts(aa, [mann_whitney()], None, sizes=(10,))
    assert set(fpr["metric"]) == set(TARGET.values()) - {"cls", "tbt"}


def test_cls_absolute_on_a_two_valued_metric():
    df = bench(0.0)
    df["cls"] = 0.15
    df.loc[df["variant"] == "pr", "cls"] = 0.17
    df["kind"], df["pct"] = "layout-shift", 10.0
    out = cls_absolute(df[df["label"] == "injected"], sizes=(10,))
    assert out["abs_effect"].round(3).eq(0.02).all()
    assert out["median >+0.01"].all() and not out["median >+0.025"].any()

"""Analysis of perfgate measurements: noise, minimum detectable effect, false alarms."""

METRICS = ["fcp", "lcp", "tbt", "cls", "si"]

# A comparison is only meaningful within one configuration.
GROUP = ["app", "runner", "throttling", "mode"]

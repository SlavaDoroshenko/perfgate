# Native application extension: feasibility, not current implementation

The reusable part is repeated baseline/candidate measurements, experiment-quality
checks, statistical comparison, multiplicity correction and reports. Browser
metrics and Lighthouse do not directly measure a native application.

The comparison kernel (`compare_samples`) already accepts named, nonnegative,
lower-is-better sample arrays with units and absolute/relative margins. The browser
adapter supplies FCP/LCP/TBT/CLS. This is a small separation of concerns, not a
claim of native platform support. Arbitrary metric directions and native traces
still need explicit adapters and validation.

| Platform | Measurement adapter to investigate | Main additional work |
|---|---|---|
| iOS / macOS | XCTest performance metrics: elapsed time, CPU, memory; launch metric where supported | Xcode builds, signing/devices, scenario automation, export of per-iteration data |
| Android | Jetpack Macrobenchmark startup/frame metrics | Gradle/instrumentation, physical devices, compilation/cache state, thermal controls |
| Windows | Scenario harness with WPR/ETW traces and extracted measurements | Build/install automation, trace processing, process attribution and machine control |
| Linux | Scenario harness, elapsed/resource time, perf where appropriate | Repeatable workloads, permissions, CPU governor/affinity and trace/counter interpretation |

Sources checked 30 October 2026:

- [Apple XCTest CPU and related performance metrics](https://developer.apple.com/documentation/xctest/xctcpumetric)
- [Apple application launch metric](https://developer.apple.com/documentation/xctest/xctapplicationlaunchmetric)
- [Android Macrobenchmark metrics](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-metrics)
- [Android Macrobenchmark lab: physical-device measurements](https://developer.android.google.cn/codelabs/android-macrobenchmark-inspect)
- [Microsoft WPR/WPA](https://learn.microsoft.com/en-us/troubleshoot/windows-server/support-tools/support-tools-xperf-wpa-wpr)
- [Linux perf workload tracing](https://kernel.org/doc/html/latest/admin-guide/workload-tracing.html)

Expected impact (engineering assessment): adding one adapter is manageable after
stabilizing the browser contract; validating all five platforms is a separate
multi-platform research programme. Device heat, battery/power mode, GPU drivers,
compilation, installation and caches can dominate variance. Alternating browser
URLs is much cheaper than repeatedly installing two mobile builds. Published
browser sensitivity and false-alarm rates cannot be transferred to those platforms.

Keep the current thesis scope on web applications. Preserve the collector/kernel
boundary and use one native platform as a future feasibility pilot. Do not promise
all-platform sensitivity, reuse browser margins, or equate simulator results with
physical-device performance. A credible extension needs its own A/A corpus,
labelled regressions, comparable resource budgets and prospective validation.

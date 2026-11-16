# Sitespeed / Lighthouse replication, 17 November 2026

Downloaded from [GitHub Actions run 43962053827](https://github.com/SlavaDoroshenko/perfgate/actions/runs/43962053827),
predeclared in `docs/protocols/sitespeed-replication-2026-11-17.md` on main. Thirty jobs:
A/A, FCP +2% and TBT +10%, ten repetitions each, tool order alternating with the
repetition number. Each tool measures ten loads per variant after two warm-ups per
variant. `manifest.json` records the code commit and SHA-256 of every file. Outside
`raw/` on purpose; derive tables with `perfgate_analysis.tool_comparison`.

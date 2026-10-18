# Sitespeed / Lighthouse pilot, 18 October 2026

Downloaded from [GitHub Actions run 39149657629](https://github.com/SlavaDoroshenko/perfgate/actions/runs/39149657629).
Nine jobs cover A/A, FCP +2% and TBT +10%, each repeated three times. Each tool
measures ten loads per variant after two warm-ups per variant.

Every artifact contains the actual sitespeed compare result (including raw
Browsertime samples), the Lighthouse JSONL records and environment/timing metadata.
`manifest.json` records the producing code commit and SHA-256 hashes of all 27
downloaded files. The archive keeps the original artifact directory structure.

These measurements belong to a tool comparison, so they are outside `raw/` and
must not enter the main noise experiment accidentally. Reproduce the derived
tables with `perfgate_analysis.tool_comparison`; see `docs/sitespeed.md` on main
for the protocol, results and limitations.

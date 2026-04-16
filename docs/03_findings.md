# Findings (Current Snapshot)

This file summarizes results produced by `scripts/analyze_sbti.py`.

## Key points

1. Mapping is deterministic, not random.
2. Personality proportions are **not uniform** under uniform answer combinations.
3. `DRUNK` gets a fixed mass from branch logic.

## Distribution highlights (full-space assumption)

Top items (example from current run):

- DRUNK: 20.0000%
- OJBK: 7.9221%
- THAN-K: 6.3514%
- FAKE: 5.3738%
- SEXY: 4.7414%
- ...
- BOSS: 1.2687%
- HHHH: 0.0386%

Please use generated CSV files in `docs/data/` as the source of truth for your run.

## Why unequal?

Because this is nearest-template partitioning in a finite 15-dim L/M/H grid.
Different templates own different “Voronoi-like” regions, so hit rates differ.

## Notes

- Values may change if the website updates question set, patterns, or branch rules.
- Always regenerate outputs after upstream changes.

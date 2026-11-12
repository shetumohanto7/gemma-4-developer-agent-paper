# Context management: gemma-4-12b, original vs `nothoughts` (pre-registered LOG 20:54)

| condition | run | resolved | context overflow | 10-min cap | empty patch | mean tool calls | median minutes | edits gold function | resolved if so |
|---|---|---|---|---|---|---|---|---|---|
| base | original | 15/86 (17.4%) | 66% | 8% | 52% | 18.0 | 3.7 | 20/73 | 13/20 |
| base | nothoughts | 15/86 (17.4%) | 48% | 19% | 49% | 19.7 | 6.7 | 22/73 | 12/22 |
| oracle_func | original | 23/86 (26.7%) | 53% | 10% | 44% | 16.1 | 5.0 | 39/73 | 22/39 |
| oracle_func | nothoughts | 26/86 (30.2%) | 36% | 27% | 45% | 16.4 | 8.1 | 36/73 | 24/36 |

## Pre-registered tests (uncorrected, 2 comparisons; task-level bootstrap CI)

- **H9a: base, nothoughts vs original** (86 tasks): +0.0 pts [-9.3, +8.1]; nothoughts-only 7 vs original-only 7, exact McNemar p = 1.0000
- **H9b: oracle_func, nothoughts vs original** (86 tasks): +3.5 pts [-4.7, +11.6]; nothoughts-only 8 vs original-only 5, exact McNemar p = 0.5811

# Find vs fix: gemma-4-12b, 86 tasks in every condition (0 excluded for infrastructure errors)

| condition | resolved | empty patch | patch touches gold file | gold function | context overflow* | mean tool calls | median minutes |
|---|---|---|---|---|---|---|---|
| base | 15/86 (17.4%) | 52% | 30% | 23% | 66% | 18.0 | 3.7 |
| spanloc | 19/86 (22.1%) | 47% | 29% | 28% | 66% | 17.5 | 4.2 |
| oracle_file | 18/86 (20.9%) | 47% | 47% | 31% | 64% | 16.6 | 4.1 |
| oracle_func | 23/86 (26.7%) | 44% | 50% | 45% | 53% | 16.1 | 5.0 |

*Exploratory, not pre-registered: the episode ended because the prompt outgrew the 32K window.

## Paired tests (pre-registered H8a-d)

- **H8a: oracle_func vs base**: +9.3 pts [+1.2, +18.6] (repo-clustered [+6.2, +13.2]); oracle_func-only 12 vs base-only 4, exact McNemar p = 0.0768
- **H8b: oracle_file vs base**: +3.5 pts [-4.7, +11.6] (repo-clustered [+2.1, +5.3]); oracle_file-only 8 vs base-only 5, exact McNemar p = 0.5811
- **H8c: spanloc vs base**: +4.7 pts [-3.5, +12.8] (repo-clustered [+2.1, +7.9]); spanloc-only 9 vs base-only 5, exact McNemar p = 0.4240
- **H8d: oracle_func vs spanloc**: +4.7 pts [-4.7, +15.1] (repo-clustered [+4.2, +5.3]); oracle_func-only 12 vs spanloc-only 8, exact McNemar p = 0.5034

## Exploratory (declared before the data was complete; not pre-registered)

Find x fix: P(resolved | final patch edits a gold function / file) per condition. The function level counts only tasks with function-level gold.

| condition | edits gold function | resolved if so | resolved if not | edits gold file | resolved if so | resolved if not |
|---|---|---|---|---|---|---|
| base | 20/73 | 13/20 | 1/53 | 26/86 | 14/26 | 1/60 |
| spanloc | 24/73 | 17/24 | 2/49 | 25/86 | 18/25 | 1/61 |
| oracle_file | 27/73 | 16/27 | 1/46 | 40/86 | 18/40 | 0/46 |
| oracle_func | 39/73 | 22/39 | 0/34 | 43/86 | 23/43 | 0/43 |

Resolved by repository:

| condition | Textualize/rich | fastapi/fastapi |
|---|---|---|
| base | 6/38 | 9/48 |
| spanloc | 9/38 | 10/48 |
| oracle_file | 8/38 | 10/48 |
| oracle_func | 11/38 | 12/48 |

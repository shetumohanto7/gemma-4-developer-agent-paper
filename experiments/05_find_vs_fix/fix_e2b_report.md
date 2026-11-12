# Find vs fix: gemma-4-e2b, 86 tasks in every condition (0 excluded for infrastructure errors)

| condition | resolved | empty patch | patch touches gold file | gold function | context overflow* | mean tool calls | median minutes |
|---|---|---|---|---|---|---|---|
| base | 3/86 (3.5%) | 35% | 34% | 27% | 29% | 7.9 | 2.9 |
| spanloc | 7/86 (8.1%) | 16% | 37% | 29% | 10% | 7.0 | 2.3 |
| oracle_file | 8/86 (9.3%) | 26% | 73% | 40% | 15% | 6.2 | 2.4 |
| oracle_func | 13/86 (15.1%) | 12% | 88% | 70% | 2% | 5.4 | 2.1 |

*Exploratory, not pre-registered: the episode ended because the prompt outgrew the 32K window.

## Paired tests (pre-registered H8a-d)

- **H8a: oracle_func vs base**: +11.6 pts [+5.8, +18.6] (repo-clustered [+10.4, +13.2]); oracle_func-only 10 vs base-only 0, exact McNemar p = 0.0020
- **H8b: oracle_file vs base**: +5.8 pts [+1.2, +11.6] (repo-clustered [+4.2, +7.9]); oracle_file-only 5 vs base-only 0, exact McNemar p = 0.0625
- **H8c: spanloc vs base**: +4.7 pts [+1.2, +9.3] (repo-clustered [+4.2, +5.3]); spanloc-only 4 vs base-only 0, exact McNemar p = 0.1250
- **H8d: oracle_func vs spanloc**: +7.0 pts [+2.3, +12.8] (repo-clustered [+6.2, +7.9]); oracle_func-only 6 vs spanloc-only 0, exact McNemar p = 0.0312

## Exploratory (declared before the data was complete; not pre-registered)

Find x fix: P(resolved | final patch edits a gold function / file) per condition. The function level counts only tasks with function-level gold.

| condition | edits gold function | resolved if so | resolved if not | edits gold file | resolved if so | resolved if not |
|---|---|---|---|---|---|---|
| base | 23/73 | 3/23 | 0/50 | 29/86 | 3/29 | 0/57 |
| spanloc | 25/73 | 6/25 | 1/48 | 32/86 | 7/32 | 0/54 |
| oracle_file | 34/73 | 6/34 | 1/39 | 63/86 | 8/63 | 0/23 |
| oracle_func | 60/73 | 12/60 | 0/13 | 76/86 | 13/76 | 0/10 |

Resolved by repository:

| condition | Textualize/rich | fastapi/fastapi |
|---|---|---|
| base | 1/38 | 2/48 |
| spanloc | 3/38 | 4/48 |
| oracle_file | 4/38 | 4/48 |
| oracle_func | 6/38 | 7/48 |

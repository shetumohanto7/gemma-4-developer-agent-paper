# Find vs fix: gemma-4-e4b, 86 tasks in every condition (0 excluded for infrastructure errors)

| condition | resolved | empty patch | patch touches gold file | gold function | context overflow* | mean tool calls | median minutes |
|---|---|---|---|---|---|---|---|
| base | 11/86 (12.8%) | 12% | 43% | 28% | 10% | 9.2 | 3.1 |
| spanloc | 10/86 (11.6%) | 5% | 51% | 41% | 8% | 8.2 | 3.1 |
| oracle_file | 14/86 (16.3%) | 8% | 87% | 48% | 13% | 7.6 | 3.1 |
| oracle_func | 20/86 (23.3%) | 0% | 97% | 79% | 1% | 6.1 | 2.6 |

*Exploratory, not pre-registered: the episode ended because the prompt outgrew the 32K window.

## Paired tests (pre-registered H8a-d)

- **H8a: oracle_func vs base**: +10.5 pts [+3.5, +17.4] (repo-clustered [+5.3, +14.6]); oracle_func-only 10 vs base-only 1, exact McNemar p = 0.0117
- **H8b: oracle_file vs base**: +3.5 pts [-3.5, +10.5] (repo-clustered [+2.6, +4.2]); oracle_file-only 7 vs base-only 4, exact McNemar p = 0.5488
- **H8c: spanloc vs base**: -1.2 pts [-7.0, +4.7] (repo-clustered [-5.3, +2.1]); spanloc-only 3 vs base-only 4, exact McNemar p = 1.0000
- **H8d: oracle_func vs spanloc**: +11.6 pts [+4.7, +19.8] (repo-clustered [+10.5, +12.5]); oracle_func-only 11 vs spanloc-only 1, exact McNemar p = 0.0063

## Exploratory (declared before the data was complete; not pre-registered)

Find x fix: P(resolved | final patch edits a gold function / file) per condition. The function level counts only tasks with function-level gold.

| condition | edits gold function | resolved if so | resolved if not | edits gold file | resolved if so | resolved if not |
|---|---|---|---|---|---|---|
| base | 24/73 | 9/24 | 1/49 | 37/86 | 11/37 | 0/49 |
| spanloc | 35/73 | 10/35 | 0/38 | 44/86 | 10/44 | 0/42 |
| oracle_file | 41/73 | 12/41 | 1/32 | 75/86 | 14/75 | 0/11 |
| oracle_func | 68/73 | 19/68 | 0/5 | 83/86 | 20/83 | 0/3 |

Resolved by repository:

| condition | Textualize/rich | fastapi/fastapi |
|---|---|---|
| base | 5/38 | 6/48 |
| spanloc | 3/38 | 7/48 |
| oracle_file | 6/38 | 8/48 |
| oracle_func | 7/38 | 13/48 |

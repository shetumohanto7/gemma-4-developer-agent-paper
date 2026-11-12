# Localization results: 300 tasks (290 with function-level gold)

## File level

| method | acc@1 | acc@3 | acc@5 | acc@10 | mrr |
|---|---|---|---|---|---|
| file-bm25 | 38.7 | 59.0 | 64.7 | 77.0 | 0.518 |
| bm25 | 54.7 | 71.3 | 76.3 | 83.7 | 0.647 |
| mention | 35.0 | 54.0 | 59.0 | 65.3 | 0.458 |
| bm25+mention | 49.3 | 71.3 | 78.0 | 85.7 | 0.620 |
| ppr | 50.0 | 68.3 | 74.7 | 79.7 | 0.610 |
| bm25+ppr | 54.3 | 70.3 | 76.3 | 84.0 | 0.646 |
| graphloc | 52.0 | 71.0 | 78.0 | 84.3 | 0.633 |
| graphloc-noprior | 48.3 | 66.0 | 71.7 | 77.7 | 0.588 |

## Function level (all gold functions/classes in top-k = acc; any = hit)

| method | acc@1 | acc@5 | acc@10 | acc@20 | hit@1 | hit@5 | hit@10 | mrr |
|---|---|---|---|---|---|---|---|---|
| bm25 | 16.2 | 37.2 | 47.9 | 56.9 | 20.0 | 43.8 | 53.1 | 0.312 |
| mention | 10.7 | 20.3 | 25.5 | 27.9 | 13.1 | 23.1 | 30.0 | 0.179 |
| bm25+mention | 15.9 | 37.2 | 47.6 | 57.9 | 19.7 | 44.8 | 54.1 | 0.314 |
| ppr | 11.7 | 35.9 | 46.9 | 54.8 | 13.4 | 40.3 | 52.1 | 0.259 |
| bm25+ppr | 17.2 | 36.6 | 47.9 | 56.9 | 20.7 | 42.8 | 52.8 | 0.313 |
| graphloc | 15.5 | 38.3 | 49.7 | 57.9 | 19.0 | 44.5 | 55.5 | 0.309 |
| graphloc-noprior | 13.8 | 33.1 | 42.4 | 50.7 | 17.2 | 39.0 | 47.6 | 0.272 |

## Paired bootstrap: graphloc minus bm25 (95% CI, percentage points)

- files acc@1: -2.7 [-7.3, +1.3] (repo-clustered [-5.3, +3.6])
- files acc@5: +1.7 [-1.3, +5.0] (repo-clustered [-2.9, +3.6])
- functions acc@5: +1.0 [-2.4, +4.8] (repo-clustered [-3.0, +3.7])
- functions acc@10: +1.7 [-1.4, +4.8] (repo-clustered [-1.5, +4.6])
- functions hit@1: -1.0 [-5.2, +3.1] (repo-clustered [-4.7, +5.0])

## Per repository (graphloc, function acc@10 / file acc@5)

- django/django (n=114): func acc@10 54.6 (baseline 53.7), file acc@5 78.9
- sympy/sympy (n=77): func acc@10 36.5 (baseline 32.4), file acc@5 74.0
- scikit-learn/scikit-learn (n=23): func acc@10 52.2 (baseline 39.1), file acc@5 87.0
- matplotlib/matplotlib (n=23): func acc@10 43.5 (baseline 43.5), file acc@5 78.3
- pytest-dev/pytest (n=17): func acc@10 50.0 (baseline 56.2), file acc@5 70.6
- sphinx-doc/sphinx (n=16): func acc@10 56.2 (baseline 56.2), file acc@5 81.2
- astropy/astropy (n=6): func acc@10 66.7 (baseline 66.7), file acc@5 100.0
- psf/requests (n=6): func acc@10 83.3 (baseline 83.3), file acc@5 100.0
- pylint-dev/pylint (n=6): func acc@10 66.7 (baseline 66.7), file acc@5 50.0
- pydata/xarray (n=5): func acc@10 40.0 (baseline 40.0), file acc@5 60.0
- mwaskom/seaborn (n=4): func acc@10 75.0 (baseline 75.0), file acc@5 75.0
- pallets/flask (n=3): func acc@10 33.3 (baseline 66.7), file acc@5 100.0

## Graph distance from seeds to gold functions (hops, capped at 3)

- from_mentions: 0: 22.6%, 1: 26.3%, 2: 26.0%, 3: 16.0%, unreached: 9.1%
- from_bm25: 0: 36.3%, 1: 22.6%, 2: 22.6%, 3: 14.0%, unreached: 4.6%

Median index+rank time per task: 21.48s; max 86.79s

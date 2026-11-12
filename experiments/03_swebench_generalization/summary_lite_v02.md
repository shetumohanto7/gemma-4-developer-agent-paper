# Localization results: 300 tasks (290 with function-level gold)

## File level

| method | acc@1 | acc@3 | acc@5 | acc@10 | mrr |
|---|---|---|---|---|---|
| file-bm25 | 38.7 | 59.0 | 64.7 | 77.0 | 0.518 |
| bm25 | 54.7 | 71.3 | 76.3 | 83.7 | 0.647 |
| mention | 34.3 | 53.7 | 59.0 | 65.3 | 0.455 |
| snippet | 12.7 | 16.0 | 17.7 | 17.7 | 0.146 |
| bm25+mention | 48.3 | 71.3 | 77.7 | 85.7 | 0.614 |
| ppr | 50.3 | 67.7 | 74.3 | 79.3 | 0.610 |
| bm25+ppr | 54.3 | 70.3 | 76.3 | 84.0 | 0.646 |
| spanloc-v0.1 | 52.0 | 71.0 | 78.0 | 84.3 | 0.633 |
| spanloc-nosnippet | 51.3 | 71.0 | 77.7 | 84.3 | 0.631 |
| spanloc-nomember | 53.3 | 69.7 | 77.7 | 84.3 | 0.639 |
| spanloc | 52.3 | 69.7 | 77.3 | 84.3 | 0.634 |
| spanloc-noprior | 48.3 | 65.3 | 71.3 | 77.7 | 0.585 |

## Function level (all gold functions/classes in top-k = acc; any = hit)

| method | acc@1 | acc@5 | acc@10 | acc@20 | hit@1 | hit@5 | hit@10 | mrr |
|---|---|---|---|---|---|---|---|---|
| bm25 | 16.2 | 37.2 | 47.9 | 56.9 | 20.0 | 43.8 | 53.1 | 0.312 |
| mention | 11.4 | 22.4 | 31.4 | 35.5 | 14.5 | 26.2 | 36.2 | 0.202 |
| snippet | 6.6 | 11.0 | 11.7 | 11.7 | 7.9 | 13.1 | 13.8 | 0.101 |
| bm25+mention | 16.6 | 39.7 | 49.7 | 58.3 | 20.3 | 46.9 | 56.2 | 0.323 |
| ppr | 14.8 | 38.3 | 47.9 | 55.5 | 17.2 | 43.8 | 53.8 | 0.290 |
| bm25+ppr | 17.2 | 36.6 | 47.9 | 56.9 | 20.7 | 42.8 | 52.8 | 0.313 |
| spanloc-v0.1 | 15.5 | 38.3 | 49.7 | 57.9 | 19.0 | 44.5 | 55.5 | 0.309 |
| spanloc-nosnippet | 15.9 | 39.7 | 51.0 | 59.3 | 19.3 | 46.2 | 57.2 | 0.317 |
| spanloc-nomember | 19.0 | 39.0 | 50.0 | 57.9 | 22.1 | 45.5 | 56.2 | 0.333 |
| spanloc | 19.0 | 40.0 | 51.4 | 59.7 | 22.1 | 46.6 | 57.9 | 0.337 |
| spanloc-noprior | 16.9 | 35.2 | 45.2 | 51.0 | 20.0 | 41.0 | 50.3 | 0.300 |

## Paired bootstrap: spanloc minus spanloc-v0.1 (95% CI, percentage points)

- files acc@1: +0.3 [-1.3, +2.0] (repo-clustered [-1.1, +1.6])
- files acc@5: -0.7 [-2.0, +0.7] (repo-clustered [-1.9, +0.0])
- functions acc@5: +1.7 [-1.0, +4.5] (repo-clustered [-0.9, +2.6])
- functions acc@10: +1.7 [-0.3, +4.1] (repo-clustered [-2.8, +3.6])
- functions hit@1: +3.1 [+0.7, +5.5] (repo-clustered [-2.7, +5.9])

## Per repository (spanloc, function acc@10 / file acc@5)

- django/django (n=114): func acc@10 59.3 (baseline 54.6), file acc@5 78.1
- sympy/sympy (n=77): func acc@10 39.2 (baseline 36.5), file acc@5 74.0
- matplotlib/matplotlib (n=23): func acc@10 34.8 (baseline 43.5), file acc@5 78.3
- scikit-learn/scikit-learn (n=23): func acc@10 52.2 (baseline 52.2), file acc@5 87.0
- pytest-dev/pytest (n=17): func acc@10 50.0 (baseline 50.0), file acc@5 70.6
- sphinx-doc/sphinx (n=16): func acc@10 56.2 (baseline 56.2), file acc@5 81.2
- astropy/astropy (n=6): func acc@10 66.7 (baseline 66.7), file acc@5 83.3
- psf/requests (n=6): func acc@10 83.3 (baseline 83.3), file acc@5 100.0
- pylint-dev/pylint (n=6): func acc@10 66.7 (baseline 66.7), file acc@5 50.0
- pydata/xarray (n=5): func acc@10 40.0 (baseline 40.0), file acc@5 60.0
- mwaskom/seaborn (n=4): func acc@10 75.0 (baseline 75.0), file acc@5 75.0
- pallets/flask (n=3): func acc@10 33.3 (baseline 33.3), file acc@5 100.0

## Graph distance from seeds to gold functions (hops, capped at 3)

- from_mentions: 0: 27.7%, 1: 21.7%, 2: 26.9%, 3: 14.6%, unreached: 9.1%
- from_bm25: 0: 36.3%, 1: 22.6%, 2: 22.6%, 3: 14.0%, unreached: 4.6%

Median index+rank time per task: 9.88s; max 37.15s

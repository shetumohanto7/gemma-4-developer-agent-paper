# Localization results: 129 tasks (107 with function-level gold)

## File level

| method | acc@1 | acc@3 | acc@5 | acc@10 | mrr |
|---|---|---|---|---|---|
| file-bm25 | 20.2 | 31.0 | 36.4 | 49.6 | 0.291 |
| bm25 | 34.9 | 46.5 | 57.4 | 65.1 | 0.449 |
| mention | 25.6 | 27.9 | 27.9 | 28.7 | 0.268 |
| snippet | 1.6 | 1.6 | 1.6 | 1.6 | 0.016 |
| bm25+mention | 32.6 | 45.7 | 55.8 | 65.1 | 0.430 |
| ppr | 31.8 | 45.0 | 52.7 | 60.5 | 0.420 |
| bm25+ppr | 33.3 | 48.8 | 57.4 | 66.7 | 0.445 |
| spanloc-v0.1 | 33.3 | 48.8 | 57.4 | 66.7 | 0.440 |
| spanloc-nosnippet | 33.3 | 48.8 | 57.4 | 66.7 | 0.440 |
| spanloc-nomember | 32.6 | 48.8 | 56.6 | 66.7 | 0.435 |
| spanloc | 32.6 | 48.8 | 56.6 | 66.7 | 0.435 |
| spanloc-noprior | 26.4 | 36.4 | 41.1 | 51.2 | 0.346 |
| spanloc@their-graph | 34.9 | 49.6 | 58.1 | 69.8 | 0.456 |

## Function level (all gold functions/classes in top-k = acc; any = hit)

| method | acc@1 | acc@5 | acc@10 | acc@20 | hit@1 | hit@5 | hit@10 | mrr |
|---|---|---|---|---|---|---|---|---|
| bm25 | 18.7 | 31.8 | 36.4 | 48.6 | 25.2 | 41.1 | 46.7 | 0.336 |
| mention | 14.0 | 19.6 | 19.6 | 20.6 | 19.6 | 26.2 | 26.2 | 0.220 |
| snippet | 0.0 | 0.9 | 0.9 | 0.9 | 0.0 | 1.9 | 1.9 | 0.008 |
| bm25+mention | 19.6 | 34.6 | 40.2 | 49.5 | 26.2 | 43.9 | 51.4 | 0.348 |
| ppr | 12.1 | 26.2 | 33.6 | 43.0 | 17.8 | 38.3 | 47.7 | 0.280 |
| bm25+ppr | 15.9 | 32.7 | 38.3 | 47.7 | 22.4 | 41.1 | 49.5 | 0.317 |
| spanloc-v0.1 | 16.8 | 34.6 | 38.3 | 47.7 | 23.4 | 44.9 | 50.5 | 0.336 |
| spanloc-nosnippet | 16.8 | 35.5 | 39.3 | 47.7 | 24.3 | 45.8 | 51.4 | 0.340 |
| spanloc-nomember | 16.8 | 33.6 | 38.3 | 46.7 | 23.4 | 44.9 | 50.5 | 0.333 |
| spanloc | 16.8 | 34.6 | 39.3 | 47.7 | 24.3 | 45.8 | 51.4 | 0.337 |
| spanloc-noprior | 14.0 | 26.2 | 28.0 | 36.4 | 20.6 | 35.5 | 38.3 | 0.278 |
| spanloc@their-graph | 14.0 | 35.5 | 40.2 | 47.7 | 19.6 | 47.7 | 51.4 | 0.313 |

## Paired bootstrap: spanloc minus bm25 (95% CI, percentage points)

- files acc@1: -2.3 [-8.5, +3.9] (repo-clustered [-14.3, +9.6])
- files acc@5: -0.8 [-4.7, +3.1] (repo-clustered [-4.4, +4.1])
- functions acc@5: +2.8 [-2.8, +8.4] (repo-clustered [+0.0, +7.0])
- functions acc@10: +2.8 [-2.8, +8.4] (repo-clustered [+0.0, +7.0])
- functions hit@1: -0.9 [-7.5, +5.6] (repo-clustered [-3.6, +10.0])

## Per repository (spanloc, function acc@10 / file acc@5)

- fastapi/fastapi (n=67): func acc@10 34.5 (baseline 34.5), file acc@5 44.8
- Textualize/rich (n=48): func acc@10 38.1 (baseline 31.0), file acc@5 64.6
- psf/requests (n=13): func acc@10 77.8 (baseline 77.8), file acc@5 84.6
- encode/httpx (n=1): func acc@10 0.0 (baseline 0.0), file acc@5 100.0

## Graph distance from seeds to gold functions (hops, capped at 3)

- from_mentions: 0: 20.5%, 1: 9.8%, 2: 9.8%, 3: 13.7%, unreached: 46.3%
- from_bm25: 0: 23.9%, 1: 16.1%, 2: 22.0%, 3: 20.5%, unreached: 17.6%

Median index+rank time per task: 2.39s; max 5.13s

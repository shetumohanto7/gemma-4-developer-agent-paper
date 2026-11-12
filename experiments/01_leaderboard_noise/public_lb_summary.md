# Public leaderboard resolution (snapshot: leaderboard_main_2026-10-22.json)

- Teams on the public LB: 3428
- Task counts N in [20, 200] consistent with all 15 distinct displayed scores: [58, 79, 86, 90, 93, 94, 95, 97, 98, 99] ... -> N = 58 public tasks; one task = 1.72 points
- Best public score: 14/58 = 0.241; teams at the max: 4
- Median non-zero team: 9/58; zero-score teams: 153

## Solved public tasks by number of submissions

| submissions | teams | median | p90 | max | binomial best-of-n bound (p = median single-submission rate) |
|---|---|---|---|---|---|
| 1 (median 1) | 592 | 6 | 10 | 13 | 6.0 |
| 2-3 (median 2) | 786 | 7 | 10 | 12 | 7.3 |
| 4-7 (median 5) | 872 | 9 | 11 | 14 | 8.8 |
| 8-15 (median 10) | 751 | 10 | 12 | 14 | 9.8 |
| 16+ (median 19) | 274 | 11 | 12 | 14 | 10.6 |

## Selection-only null model at the leaderboard's modal score

For an agent solving each public task with probability p = 0.172 (10/58, the modal score), a single run has SD <= 2.88 tasks (binomial bound). Expected best public score after m identical re-submissions (upper bound; heterogeneity lowers it):

- m =  1: 10.0/58 = 0.172
- m =  2: 11.6/58 = 0.200
- m =  5: 13.4/58 = 0.231
- m = 10: 14.6/58 = 0.251
- m = 20: 15.6/58 = 0.269
- m = 40: 16.6/58 = 0.286

## Histogram of solved public tasks

| solved | teams |
|---|---|
| 0 | 153 |
| 1 | 66 |
| 2 | 109 |
| 3 | 144 |
| 4 | 156 |
| 5 | 219 |
| 6 | 275 |
| 7 | 310 |
| 8 | 350 |
| 9 | 480 |
| 10 | 555 |
| 11 | 424 |
| 12 | 148 |
| 13 | 35 |
| 14 | 4 |

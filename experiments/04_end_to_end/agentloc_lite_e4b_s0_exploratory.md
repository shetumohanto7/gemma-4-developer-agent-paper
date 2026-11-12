# Exploratory (not pre-registered): agent vs the ranking it was given

| condition | mean locations submitted | episodes submitting 0 | function hit |
|---|---|---|---|
| base | 0.97 | 11% | 20.7% |
| skill | 1.07 | 12% | 32.0% |
| inject | 1.04 | 9% | 30.0% |

- skill: agent function hit 33.1% vs spanloc alone at the same number of locations 22.8% (290 tasks with function gold); agent-only 55, spanloc-only 25

- inject: agent function hit 31.0% vs spanloc alone at the same number of locations 23.8% (290 tasks with function gold); agent-only 48, spanloc-only 27
- spanloc alone Hit@1 / Hit@5 on these tasks: 22.1% / 46.6%

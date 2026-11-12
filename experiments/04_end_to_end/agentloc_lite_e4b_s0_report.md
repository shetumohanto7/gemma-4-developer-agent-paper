# Agentic localization: gemma-4-e4b-it-qat-w4a16-ct, 300 task-seeds, conditions ['base', 'skill', 'inject']

| condition | episodes | infra failures | function hit | lenient hit | file hit | median prompt tokens | mean tool calls | fallback parse | turn limit | no tool call | overflow |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 300 | 0 | 20.7% | 24.0% | 55.3% | 33080 | 11.6 | 4% | 14% | 1% | 0% |
| skill | 300 | 0 | 32.0% | 32.7% | 60.7% | 20856 | 10.4 | 9% | 13% | 7% | 0% |
| inject | 300 | 0 | 30.0% | 31.0% | 59.3% | 19803 | 11.0 | 4% | 12% | 1% | 0% |

## Paired tests against base (pre-registered H7a, H7b, H7c)

- **skill vs base** (300 pairs): function hit +11.3 pts [+6.3, +16.7] (repo-clustered [+2.2, +14.9]); discordant skill-only 52 vs base-only 18, exact McNemar p = 0.0001
  prompt tokens per episode -11830 [-16169, -7597] (repo-clustered [-18748, -6007])
- **inject vs base** (300 pairs): function hit +9.3 pts [+4.3, +14.3] (repo-clustered [+2.7, +13.1]); discordant inject-only 44 vs base-only 16, exact McNemar p = 0.0004
  prompt tokens per episode -15522 [-19437, -11510] (repo-clustered [-19026, -12056])

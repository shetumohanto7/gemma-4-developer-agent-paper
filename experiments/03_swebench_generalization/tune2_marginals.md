# Grid 2 marginal effects (dev split, 391 tasks with function gold)

Rule (LOG 13:15): keep a feature if best-with minus best-without >= +0.5 Acc@10 or >= +1.0 Hit@1.

| feature | best Acc@10 with | best Acc@10 without | Δ | best Hit@1 with | best Hit@1 without | Δ | keep? |
|---|---|---|---|---|---|---|---|
| snippet | 45.8 | 45.3 | +0.5 | 28.6 | 27.9 | +0.8 | yes |
| strip | 45.8 | 45.8 | +0.0 | 28.4 | 28.6 | -0.3 | no |
| member | 45.8 | 44.2 | +1.5 | 28.6 | 28.1 | +0.5 | yes |

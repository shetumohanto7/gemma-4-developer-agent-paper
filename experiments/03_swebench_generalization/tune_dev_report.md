dev split: 407 tasks (391 with function gold); quoted-line signal fired on 165

| rank | config | func acc@1 | acc@5 | acc@10 | hit@1 | mrr | file acc@1 | file acc@5 |
|---|---|---|---|---|---|---|---|---|
| 1 | ppr=0.6,alpha=0.2,mention=1.0,snippet=1.0 | 16.1 | 35.0 | 45.0 | 26.3 | 0.382 | 40.5 | 69.3 |
| 2 | ppr=1.0,alpha=0.35,mention=1.0,snippet=1.0 | 16.1 | 35.0 | 44.8 | 26.6 | 0.383 | 40.5 | 70.0 |
| 3 | ppr=0.6,alpha=0.2,mention=1.0,snippet=2.0 | 16.4 | 34.5 | 44.8 | 26.3 | 0.381 | 39.6 | 69.0 |
| 4 | ppr=1.0,alpha=0.35,mention=1.0,snippet=2.0 | 16.4 | 34.8 | 44.5 | 26.6 | 0.383 | 39.6 | 69.8 |
| 5 | ppr=0.6,alpha=0.2,mention=1.0,snippet=0.0 | 15.3 | 34.8 | 44.5 | 25.6 | 0.372 | 40.0 | 69.8 |
| 6 | ppr=1.0,alpha=0.2,mention=1.0,snippet=1.0 | 15.6 | 35.0 | 44.5 | 25.6 | 0.376 | 40.0 | 69.3 |
| 35 | ppr=0.6,alpha=0.35,mention=1.0,snippet=0.0 (reference) | 15.9 | 34.8 | 43.7 | 26.1 | 0.377 | 40.0 | 70.3 |

selected by rule: ppr=0.6,alpha=0.2,mention=1.0,snippet=1.0  (Δacc@10 vs default = +1.3 pts)

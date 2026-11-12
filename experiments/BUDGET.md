# GPU budget ledger (Modal, personal `shetu` workspace)

Credit: **$30**. Plan to spend at most about **$20**, keeping the rest as margin.
L4 price: $0.000222/s = **$0.80/h** (modal.com/pricing, 2026-10-22).
CPU: $0.0000131/core/s.

The rows below are estimates from wall-clock GPU container time,
including startup and the 5-minute idle scale-down. **Authoritative
figures are Modal's own billing records**, saved by
`scripts/snapshot_costs.sh` to `experiments/costs/`.

- First snapshot (2026-10-23 00:11, complete hours to 23:59): metered
  **$0.5806** in total.
  - g4paper-vllm: L4 $0.4502, CPU $0.0646, memory $0.0152, egress $0.0026.
  - g4paper-weights (downloads): $0.0480.
- Billing summary: $0.71 of credit used, $0.00 billed. Volume storage of
  $1.20 is covered by free storage.

| When (local) | What | L4 time | Est. cost | Running total |
|---|---|---|---|---|
| 22:58–23:20 | Image builds, weight downloads (CPU only) | 0 | ~$0.05 | $0.05 |
| 23:07–23:19 | E4B first start, crashed (transformers mismatch); app stopped | ~12 min | $0.16 | $0.21 |
| 23:36–23:41 | E4B smoke test (244 s cold start + tests); app stopped | ~5 min | $0.07 | $0.28 |
| 23:41–23:50 | E4B pilot through the Modal endpoint (agentloc) | ~9 min | ~$0.12 | ~$0.40 |
| 23:50–02:34 | E4B agentic localization, 900 episodes, 8 workers (+1 infrastructure retry at 02:33) | ~2 h 45 min | ~$2.20 | ~$2.60 |
| 02:56–~03:05 | 12B smoke test (220 s cold start, 4 requests, 5-minute idle scale-down) | ~9 min | ~$0.12 | ~$2.72 |

- **Reconciled with Modal's records (2026-10-23 03:02, complete hours to 02:59;
  `costs/billing_2026-10-23T030213+0600`):** metered **$3.10** for the deployed apps
  (g4paper-vllm $3.05: L4 $2.64, CPU $0.29, memory $0.12, egress < $0.01; g4paper-weights $0.05, mostly egress)
  plus $0.04 ephemeral. L4 by hour: 23:00 $0.45, 00:00 $0.80, 01:00 $0.80, 02:00 $0.58.
  Billing summary: **$3.14 of credit used**, $0.00 billed. The row estimates above undercount CPU and memory,
  which add ~16% to the L4 cost (0.41 / 2.64).
- **Projection for the fix experiment** (LOG 02:58): the 10-minute wall-clock cap bounds each episode, so one
  model costs at most about N_valid × 4 conditions × 10 min ÷ 8 concurrent episodes of L4 time, plus ~16% for
  CPU and memory. For ~75 valid tasks: ≤ 6.3 h ≈ **≤ $5.8 per model**. To be replaced by the pilot's measured cost.
| 03:51–04:26 | Fix pilot: attempt 1 (void, harness bug), attempt 2 (16 episodes), 2 redirect tests (150 s, 304 s) | ~35 min | ~$0.50 | ~$3.2 |
| 04:22–06:56 | Full E4B fix run, 344 episodes, 8 concurrent | ~2 h 35 min | ~$2.40 | ~$5.6 |
| 06:56–07:12 | 12B fix run on one L4 (void: time-starved, 8 episodes) | ~20 min incl. cold start | ~$0.30 | ~$5.9 |
| 07:13–~11:20 | 12B smoke test + fix run on one A100-40GB ($2.10/h), 344 episodes | ~4 h | ~$9.3 (incl. CPU/memory) | ~$16.1 |
| 08:18–08:33 | E2B smoke test (L4; 10 min waiting for capacity, not billed while pending) | ~5 min running | ~$0.07 | |

- **Reconciled (2026-10-23 05:02, complete hours to 04:59; `costs/billing_2026-10-23T050215+0600`):**
  metered **$4.28** (L4 $3.67, CPU $0.40, memory $0.17, egress $0.04). L4 by hour: 03:00 $0.24, 04:00 $0.80.
  Billing summary: **$4.38 of credit used**, $0.00 billed.
- **Reconciled (2026-10-23 08:02, complete hours to 07:59; `costs/billing_2026-10-23T080201+0600`):** metered
  **$8.18** (L4 $5.58, A100-40GB $1.61, CPU $0.67, memory $0.28, egress $0.04). Billing summary: **$8.43 of
  credit used**, $0.00 billed. Projection: 12B finishes ~10:40 (≈ +$6.3) → ≈ $14.7; then E2B on L4 (≈ $2) →
  ≈ $16.7, within the $20 plan.
- **Reconciled (2026-10-23 11:02, complete hours to 10:59; `costs/billing_2026-10-23T110211+0600`):** metered
  **$15.01** (A100-40GB $7.91, L4 $5.72, CPU $0.96, memory $0.37, egress $0.04). Billing summary: **$15.24 of
  credit used**, $0.00 billed. 12B finishes ~11:20 (≈ +$0.8). **E2B decision:** on the L4, ≈ 2–2.5 h ≈ $2.0–2.3, giving
  a total of ≈ $18.3 < $20, so it runs. Guard: if the pace after its first hour projects past $20, stop and log.
| 11:24–14:32 | E2B fix run on one L4, 344 episodes (allocation wait ~15 min, not billed) | ~3 h | ~$2.9 | ~$18.8 |

- **Final reconciliation (2026-10-23 15:03, complete hours to 14:59; `costs/billing_2026-10-23T150319+0600`):**
  metered **$18.84** (A100-40GB $8.96, L4 $8.09, CPU $1.25, memory $0.51, egress $0.04). Billing summary: **$18.85
  of the $30 credit used**, $0.00 billed. No containers running. All GPU work is done, within the $20 plan.
| 20:54–21:10 | 12B context experiment, first attempt (stopped by its $7 guard; 8 episodes, set aside) | ~20 min | ~$0.80 | |
| 21:39–00:56 | 12B context experiment, full rerun (user authorized up to the $30 credit), 172 episodes on the A100 | ~3.3 h | ~$7.3 | ~$26.9 |

- **Final reconciliation (2026-10-24 01:03; `costs/billing_2026-10-24T010313+0600`):** metered **$26.93**
  (A100-40GB $16.62, L4 $8.09, CPU $1.57, memory $0.61, egress $0.04). Billing summary: **$26.94 of the $30 credit
  used**, $0.00 billed. No containers running. The credit guard (threshold $29.50) stays on.
- **October closed (2026-11-02 00:39; `costs/billing_2026-10_final_*.summary.{json,txt}`):** credits used
  **$26.89**, billed **$0.00**; metered $28.13 including volume storage $1.20 (free storage) and egress $0.04
  (allowance). The paper's $26.93 is compute + egress from the 2026-10-24 hourly report and agrees.

## November 2026 (Main Track; same `shetu` workspace, monthly credit reset)

Credit: $30 (Modal monthly). Guard v2 (`scripts/credit_guard.sh`, JSON parser, stops every app) at **$29.50 month
to date**, or at the first billed cent. Spent as of 2026-11-02 00:41: **$0.00**. Main Track ledger:
`../gemma-4-developer-agent/experiments/BUDGET.md`.

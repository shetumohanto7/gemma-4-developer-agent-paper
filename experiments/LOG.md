# Experiment log

Decisions are recorded **before** the results they could influence, so the
paper can state exactly what was tuned on what. Times are local (UTC+6),
taken from file modification times and command output; "~" marks times
reconstructed to the nearest few minutes.

## 2026-10-22

> Correction (12:55): a first draft of this log carried timestamps (13:05–13:40)
> that were later than the actual clock. They were placeholders, not
> measurements. The times below are the real ones. The order of events was
> never different.

- **~12:28 — graphloc v0.1 defaults set a priori** (no evaluation run yet):
  BM25 k1=1.2, b=0.75; name tokens ×3, signature ×2; fusion weights
  bm25=1.0, mention=1.0, ppr=0.6; PPR restart α=0.35, 30 BM25 seeds;
  mention weights trace 3.0 / path 2.0 / dotted 2.5 / backtick 2.0 / plain 1.0;
  path prior tests ×0.3, docs/examples ×0.5.
- **12:34 — smoke test on SWE-bench Lite `psf/requests` (6 tasks)**. Pipeline
  works; index build 0.3 s/task. Two changes made after looking at these six
  tasks (both are a-priori-justifiable, logged here for transparency):
  1. vendored code (`packages/`, `vendor/`, `_vendor/`, `extern(als)/`,
     `third_party/`) gets the same ×0.3 prior as tests: requests ships
     `requests/packages/urllib3`, which crowded the top-10;
  2. `SyntaxWarning`s from `ast.parse` are suppressed (they would leak into the
     agent's tool output).
  **v0.1 frozen at this point (core.py 12:34:37).**
- **Protocol for any further tuning:** tune only on SWE-bench Verified tasks
  that are *not* in SWE-bench Lite; report SWE-bench Lite and the competition's
  129 public tasks as held-out evaluations, run once with frozen settings.
- **~12:39 — v0.1 on Lite, 8 repos (134 tasks; results_lite.jsonl).**
  Entity-level BM25 aggregated to files beats whole-file BM25 (file Acc@1
  49.3 vs 36.6). graphloc minus bm25: function Acc@5 +3.1 [−1.5, +8.5], not
  significant. 80% of gold functions lie within 2 hops of BM25 seeds.
- **12:43 — Lite, django/astropy/sklearn added (277/300 tasks).**
  matplotlib clone still running at that time.
- **~12:42 — idea for a v0.2 signal (quoted code lines)** came from looking
  at one Lite task (psf__requests-2317) while smoke-testing the skill. The
  issue quotes the buggy line verbatim. To keep Lite held out, the signal's
  weight and the fusion grid (ppr ∈ {0, .3, .6, 1}, α ∈ {.2, .35, .5},
  mention ∈ {.5, 1}, snippet ∈ {0, 1, 2}) are chosen **only** on the dev split
  (`locbench/tune.py` 12:44, 407 Verified-minus-Lite tasks).
- **~12:46 — Lite rerun with frozen v0.1 recording candidate spans** for the
  budgeted metric (`results_lite_v01.jsonl`; same rankings as before plus
  sizes). This file supersedes `results_lite.jsonl`. matplotlib excluded until
  its clone finished (it finished ~12:47); it is added afterwards by resume.
- **12:53 — v0.2 selection rule (fixed before reading `tune_dev.jsonl`):**
  among the 60 grid configs, pick the one with the highest dev-split function
  Acc@10 (mean over tasks with function-level gold); break ties by Hit@1,
  then by fewer non-default changes. If the best config beats v0.1 defaults
  by < 1 point Acc@10, keep v0.1 fusion weights and change only what clears
  that bar.
- **12:54 — interim look at the dev split (87 tasks, failure analysis).**
  Grid is flat (most configs within ~1 point Acc@10). Failure patterns on
  dev: (a) a class is named, the edit is in one of its methods; (b) GitHub
  issue-template HTML comments dilute the query; (c) the issue names a
  public entry point, the edit is 2+ calls deeper. (a) and (b) motivate two
  more v0.2 candidates, to be added as a second dev-split grid *after* the
  first grid finishes: strip `<!-- -->` comments; pass a named class's
  mention score to its methods weighted by their BM25.

- **13:15 — grid 2 selection rule (fixed before running `locbench/tune2.py`).**
  Grid 2 crosses ppr ∈ {0.3, 0.6} × quoted-line snippet ∈ {0, 1} × strip
  issue-template comments ∈ {0, 1} × class→method member expansion ∈
  {0, .5, 1} (α = 0.35, mention = 1 fixed), on all 407 dev tasks.
  - **v0.2 = the grid-2 config with the highest dev function Acc@10.** Ties
    break by Hit@1, then by fewer changes from v0.1 (ppr 0.6, snippet 0,
    strip 0, member 0).
  - A feature is **kept only if** its marginal effect (best config with it
    minus best config without it) is ≥ +0.5 Acc@10 or ≥ +1.0 Hit@1 on dev.
    Otherwise it is dropped and reported as not helpful.
  - v0.2 is then frozen and run **once** on SWE-bench Lite and once on the
    competition tasks.

- **13:30 — grid 2 finished; v0.2 selected by the 13:15 rule.** The best
  dev config was ppr 0.6, quoted-line snippet 1, strip 0, member 1: function
  Acc@10 45.8 vs 43.7 for v0.1 (+2.0), Hit@1 27.6 vs 26.1. Marginals: snippet
  +0.5 Acc@10 / +0.8 Hit@1 (kept, at the bar); member +1.5 / +0.5 (kept);
  strip +0.0 / −0.3 (dropped). Files: `tune2_dev_report.md`,
  `tune2_marginals.md`. Grid 1 (all 407 dev tasks, `tune_dev_report.md`)
  preferred α = 0.2 by +0.4 Acc@10; α stays 0.35 because the rule names the
  grid-2 argmax.
- **13:32 — tool renamed graphloc → spanloc.** A public paper-track notebook
  is already called "GraphLoc". Results files written before this keep the
  method key `graphloc` (= spanloc v0.1).
- **13:36 — spanloc v0.2 frozen**: `spanloc/core.py` sha256 6a4967b468fa9869…,
  `spanloc/cli.py` a841da6b48645260…. Port verified exact: on 18 dev tasks,
  gold ranks under `spanloc` and `spanloc-v0.1` equal the tuning scripts'
  ranks for the selected and the v0.1 configs (0 mismatches). Next: one
  run on SWE-bench Lite (`results_lite_v02.jsonl`), with v0.1 and the
  ablations recomputed in the same run for paired comparison.

### Results, frozen v0.2, SWE-bench Lite held out, one run (13:44, from `date`)

Files: `results_lite_v02.jsonl`, `summary_lite_v02.{md,json}`,
`budget_lite_v02.{md,json}`, `h4_quoted_lines_lite.md`.

- **Integrity:** `spanloc-v0.1` recomputed in this run reproduces the v0.1 run
  on 300/300 tasks.
- **v0.2 vs v0.1 (paired, 290 tasks with function gold):**
  - function Hit@1 +3.1 [+0.7, +5.5] (repo-clustered [−2.7, +5.9]);
  - Acc@10 +1.7 [−0.3, +4.1] (repo-clustered [−2.8, +3.6]);
  - file Acc@1 +0.3, n.s.
  - So the dev gain largely survives at task level, but is not significant
    once repositories are clustered.
- **v0.2 vs function BM25:** Acc@10 +3.4 [+0.0, +6.9] (repo-clustered
  [−3.6, +6.1]). Absolute v0.2: function Acc@10 51.4, Hit@1 22.1,
  Hit@10 57.9; file Acc@1 52.3, Acc@5 77.3.
- **H4 confirmed:** the quoted-line signal fires on 96/290 tasks (33%). On
  those, function Hit@1 is 28.1% vs 19.8% without it (10 vs 2 discordant
  pairs, exact McNemar p = 0.039).
- **Budget metric:** v0.2 does not beat function BM25 (median tokens to the
  first gold 3,678 vs 3,447; first-gold@4K 51.7% vs 53.4%). Rank gains come
  partly from promoting larger entities. Checked at 13:46: median tokens of
  the top-5 candidates are 2,792 (v0.2) and 3,113 (v0.1) vs 2,689 (BM25), and
  spans > 150 lines in the top-5 average 0.68 / 0.73 vs 0.56 per task. H2's
  contrast with whole files is unchanged (27,535 tokens).
- **Reporting fix (13:42):** methods that return no candidates now count as
  misses in every average (`report.task_ranks`). Before the fix, the
  mention-only and snippet-only rows were averaged over the tasks where they
  fired. Main methods are unaffected because they always return output; both
  summaries were regenerated.

- **~14:20 — Ollama updated 0.23.2 → 0.40.8; `gemma4:e4b-it-qat`
  pulled.** It is Q4_0 QAT, with tools and thinking, defaults T 1.0 /
  top_p 0.95 / top_k 64, and the `gemma4` parser.
- **Pilot:** 3 Lite tasks × base/skill/inject, `pilot_e4b.jsonl`. The pipeline
  works; 0/9 function hits. Two harness-fidelity fixes followed: up to 3
  nudges (as in swegemma), and parsing locations from the last assistant
  text when `submit_locations` is never called (flagged `fallback_parse`).

## Direction (2026-10-22, evening)

Decision: go ahead with the remaining steps.
Direction: **find vs. fix for small Gemma 4 agents**.
- **Find (local):** agentic localization on SWE-bench Lite.
- **Fix (needs competition data):** oracle-location interventions in the
  official harness.

### Pre-registration: agentic localization ("find"), E4B, SWE-bench Lite (22:38, before any run)

- **Design:**
  - all 300 Lite tasks × conditions {base, skill, inject} × seed 0;
  - `gemma4:e4b-it-qat` via Ollama 0.40.8, thinking **off**, temperature 0.2
    (the official sample submission's value), num_ctx 32768, ≤ 20 tool calls;
  - read-only Docker sandbox; spanloc v0.2 (frozen 13:36) as the skill;
  - output: `experiments/04_end_to_end/agentloc_lite_e4b_s0.jsonl` (+ shards).
- **Primary outcome:** function hit (any submitted function is gold),
  strict. Secondary: lenient hit (a submitted class contains a gold method),
  file hit, prompt tokens, tool calls, fallback_parse rate.
- **Hypotheses:**
  - H7a: inject > base on function hit.
  - H7b: skill > base on function hit.
  - H7c: inject uses fewer prompt tokens than base.
- **Tests:** exact McNemar on paired task outcomes; paired bootstrap
  (task-level and repo-clustered) for differences; α = 0.05 per
  hypothesis, no multiplicity correction (3 pre-specified tests, reported
  as such).
- A second seed and a thinking-on replicate are optional follow-ups,
  labelled as such if run.

- **22:51 — local model runs stopped; local models deleted.**
  - The E4B "find" run above ended with the previous session after 1
    episode (`agentloc_lite_e4b_s0.shard0.jsonl`). That episode is not
    analysed and the run is void.
  - All Ollama models (gemma4 e2b/e4b, embeddinggemma, a partial 12b) and
    temporary repo checkouts were removed.
  - Model runs move to **Modal GPUs** (account still to be confirmed).
    The 22:38 pre-registration (design, outcomes, H7a–c) carries over
    unchanged, except the model is served by vLLM from the competition's own
    W4A16 checkpoint instead of an Ollama Q4_0 build. That is a fidelity
    gain, and is logged here before any run.

- **23:00–23:20 — Modal set up (personal `shetu` workspace only; GPU on Modal, CPU on the Mac).**
  - The token is stored in profile `shetu` with `--no-activate`; the active
    profile stays unchanged. Every Modal module refuses to run unless
    `MODAL_PROFILE=shetu`.
  - **GPU image:** the scorer's patched `vllm-0.19.1` wheel from the public
    wheelhouse (sha256 73c69bafca24fbda…), served with adk_submission
    0.2.13's `VllmServer.build_cmd` flags (`modal_app/vllm_server.py`).
    Differences from the scorer: TP=1 on one L4 instead of 4×L4, plus an
    API key.
  - **Weights:** the competition W4A16 checkpoints are in Modal volume
    `g4paper-models`; E4B is 11.55 GB, 9 files.
  - **Blocker:** Modal requires a payment method on the workspace before
    any L4 function can run ("Please add a payment method to use L4 GPU
    functions"), even with credit available. No GPU has run; spend so far
    is only CPU download containers.
  - **Agent loop (`agentloc/agent.py`):** gained an OpenAI-compatible client
    (vLLM API, thinking via `chat_template_kwargs`, tool results linked by
    `tool_call_id`, retries, context overflow recorded as its own outcome),
    plus parallel workers (`--workers`). Offline tests:
    `tests/test_agent_loop.py`.

- **23:07–23:41 — GPU bring-up on Modal (`shetu`), after adding a payment method.**
  - **First start crashed.** Unpinned pip pulled `transformers` 5.20.2, and
    vLLM 0.19.1 raised `head_dim is a per-layer attribute`. The app was
    stopped at once (≈12 L4-minutes lost).
  - **Image fix:** the scorer's exact serving wheels from wheelhouse v31 are
    overlaid with `--no-deps` on top of the vLLM install (transformers
    5.13.1, tokenizers 0.22.2, xgrammar 0.2.5.post1, compressed-tensors
    0.15.0.1, flashinfer 0.6.6, …). PyPI pins: huggingface_hub < 2,
    nvidia-cutlass-dsl 4.6.2, cuda-bindings 12.9.4. The wheelhouse's own
    declared requirements conflict (xgrammar wants transformers < 5), so it
    cannot be installed with dependency resolution. A fail-fast launcher now
    stops the container if vLLM exits during startup.
  - **Smoke test (E4B, one L4):**
    - cold start 244 s;
    - a request without the key gets HTTP 401;
    - the gemma4 tool-call parser returns a well-formed call (3.7 s);
    - thinking works (reasoning returned separately).
  - **Key exposure fixed:** vLLM logs its non-default args, which included
    `--api-key`. The key now reaches vLLM only through the `VLLM_API_KEY`
    environment variable, and it was rotated (23:41). The logged key is dead.

- **23:50 — full E4B "find" run started:** 300 Lite tasks × base/skill/inject,
  vLLM on Modal L4, 8 local workers (`agentloc_lite_e4b_s0.jsonl`). The
  pre-registration of 22:38 applies unchanged.

## 2026-10-23

- **00:10–00:20 — reproducibility records.**
  - Every runner now writes `experiments/manifests/<run>.json`: command,
    code hashes, packages, times, output sha256 (`locbench/provenance.py`).
    Runs that predate this got retroactive manifests (marked
    `retroactive`).
  - Modal billing snapshots: `scripts/snapshot_costs.sh` →
    `experiments/costs/`.
  - Provenance (`scripts/capture_provenance.py`): checkpoint revisions E4B
    6cd26aaa…, 12B 1d2c2d7f…, E2B 971342c0…; SWE-bench Lite 6ec7bb89…,
    Verified c104f840…; wheel hashes; sandbox image 50c0876a…; machine;
    package lists.
  - Temporary artifacts copied in, with secrets redacted: Modal logs, smoke
    test, wheelhouse file list. The forum snapshot went to `data/` (local
    only).
  - Paper tables are generated by `paper/make_repro_tables.py`.

- **00:33 — infrastructure-failure handling for the E4B find run** (decided before looking at any outcomes).
  - Episode django__django-11039/skill ended with "model call failed: Remote
    end closed connection without response" (http.client
    `RemoteDisconnected`, which the retry loop did not catch). It is 1 of
    165 episodes so far.
  - Fixes for later runs:
    - `_post` now also retries ConnectionError/HTTPException;
    - `--retry-infra-failures` re-runs only episodes whose recorded result is
      an infrastructure failure;
    - `agentloc.report.load` keeps the re-run row and leaves the failed
      row in the file as an audit trail.
  - After the main run, infrastructure failures are re-run once with the
    same settings. Any that fail again are excluded pairwise, as
    pre-registered.

- **00:57 — competition data downloaded** (read-only; 21 GB unpacked in git-ignored `data/competition/`).
  It holds 129 tasks (fastapi 67, rich 48, requests 13, httpx 1), 129 snapshots, 127 commit-named graphs and embeddings,
  124 wheels, HARNESS_README, sample_submission and docker files. The task-named graph links described on the data
  page are absent; loaders map each task to `<repo>_<base_commit>` (all 129 resolve).
- **00:58 — spanloc v0.2 (frozen 13:36) run once on the 129 competition tasks** (`locbench.run_competition`,
  CPU, 3 workers) → `experiments/02_competition_localization/results.jsonl`. It includes propagation over the
  competition graph (`spanloc@their-graph`) and node/edge agreement.

- **01:00 — Results: frozen spanloc v0.2 on the 129 competition tasks (held out, one run).**
  Files: `experiments/02_competition_localization/{results.jsonl,summary.md,budget.md}`; manifest
  `competition_localization_v02`. 107 tasks have function-level gold.
  - **H1 replicates:** file Acc@1 34.9 (function BM25 aggregated) vs 20.2 (whole-file BM25).
  - **H2 replicates:** median tokens to first gold 5,954 (function BM25) vs 48,954 (whole files), 8.2× fewer
    (SWE-bench Lite: 8.0×).
  - **H3 holds:** spanloc − BM25 function Acc@10 +2.8 [−2.8, +8.4], n.s.
  - **H4 does not transfer:** the quoted-line signal fires on ~2% of competition issues (33% on Lite), so it
    contributes ~nothing here.
  - **Token cost:** fusion promotes large classes (fastapi, rich); median tokens to first gold 20,788 for v0.2
    vs 5,954 for function BM25. Rank gains ≠ token gains.
  - **H6, the competition graph vs our AST graph:**
    - 82.1% of their node ids match our entities; unmatched ids include docs_src modules named without the
      prefix;
    - 50.0% of their edges (between matched nodes) are in our AST graph;
    - their graph has a single edge type (`calls`);
    - 178/205 gold functions (86.8%) exist in their graph.
  - **Propagation over their graph** (`spanloc@their-graph`): best file Acc@10 (69.8), worse function Hit@1
    (19.6 vs 24.3).
  - **Path prior:** removing it costs 11.3 function Acc@10 points (39.3 → 28.0).
  - **Hops from the BM25 top-10:** 62% of gold functions within 2 hops; 17.6% not reached within 3.

- **01:17 — interim look at the running E4B find run (417/900 episodes).** No decision depends on it: no early
  stopping, no change to design, settings or analysis. The pre-registered tests run only on the complete data.
- **01:14 — official sandbox image `swebench-sandbox:latest` built** (b296447d7f80, linux/amd64 emulated;
  log `experiments/05_find_vs_fix/sandbox_image_build.log`).
- **Reference-patch pilot (3 tasks):** rich passes; fastapi fails (`No module named 'typing_inspection'`, missing
  from the public wheels); requests fails 4/206 tests (looks like an installed package shadowing /workspace).
  The full 129-task check is running. Any environment repair will be decided from its results, logged before any
  agent run, and applied identically to all conditions.

- **01:39 — local environment validity: diagnosis and repair (before any fix-experiment agent run).**
  - **Reference-patch check, original environment:** 74/129 done when the session restarted, now resuming.
    - fastapi 1/52 pass: 49 fail on `No module named 'typing_inspection'` (pydantic 2.13.4 requires
      typing-inspection>=0.4.2, absent from the public wheels), 2 on `dirty_equals`.
    - requests 3/8 pass; rich 12/14 pass.
  - **Mechanism (read from swegemma 0.2.11 `container_setup.py`):**
    - every wheel under 16 MB in the wheels dir is unpacked into site-packages, including the projects under
      test (requests 2.33/2.34, rich 15.0.0, fastapi 0.141.1, httpx 0.28.1);
    - flat-layout repos (rich, fastapi) are imported from `/workspace` (pytest rootdir first on sys.path);
    - src-layout `requests` is shadowed by the installed newer release, so its tests may not exercise
      `/workspace` at all.
  - **Repair (`scripts/repair_env.py`, record `experiments/05_find_vs_fix/env_repair.json`):**
    `data/competition_repaired/` holds the original wheels (hard links) plus `typing_inspection` 0.4.4 and
    `dirty_equals` 0.11 (pure Python, PyPI sha256 verified). Nothing else is changed, and the repair applies
    identically to all conditions.
  - **Validity rule, extended before any agent run** (standard fail-to-pass check): a task is valid iff its
    reference patch PASSES **and** the empty patch FAILS (`--skip-agent-patch`), both in the repaired
    environment with the official pipeline. This catches tasks whose tests pass regardless of the fix
    (e.g. through shadowing).

- **01:52 — reference-patch check, original public environment: complete. 43/129 pass**, matching the
  community's lower bound of 43–52/129.
  - Per repository: rich 39/48, fastapi 1/67, requests 3/13, httpx 0/1.
  - Failure causes: missing `typing_inspection` 62, tests fail with the reference patch 17,
    `dirty_equals` 4, `attr` 1, other 2.
  - Note: `swegemma eval` rewrites `task_results.jsonl` on restart, so the per-task rows of part 1 (74
    tasks) were overwritten by part 2 (55 tasks). Part 1's counts are in the entry above; the test logs
    remain in `gold_validation/test_outputs/`. The repaired-environment checks write to fresh folders.

- **02:02 — repaired-environment check voided and restarted: stale-cache bug in swegemma 0.2.11.**
  - swegemma caches the unpacked base-wheel bundle at `$TMPDIR/swegemma_sp_cache_v8/sp_base.tar`, keyed only
    by name. The bundle built at 01:14 from the *original* wheels was silently reused for the "repaired" run:
    after 41 tasks, 25 still failed on `typing_inspection`.
  - Those results are moved to `experiments/05_find_vs_fix/void/` and not used.
  - Fix: `scripts/run_validity_checks.sh` sets `TMPDIR=data/tmp_swegemma_<sha256 of the wheel list>`, so any
    change to the wheel set forces a fresh bundle; the original runs' cache is left as it was.
  - Also added `attrs` 26.1.0, since the original-environment logs showed module `attr` missing for 1 task
    (same evidence rule).
  - Restarted: wheel set 3af7b647cbf9.
  - Paper note: local reproductions with a modified wheel set must clear or re-key this cache.

- **02:08 — second repair round (same evidence rule).**
  - With the fresh cache, `typing_inspection` errors are gone, but 5 of the first 10 fastapi reference checks
    failed with `No module named 'inline_snapshot'`.
  - Added `inline-snapshot` 0.36.1 and its missing runtime dependencies `asttokens` 3.0.2 and `executing` 2.3.0
    (rich, typing-extensions and pytest were already present; tomli is only needed for Python < 3.11).
    All are pure Python and sha256-verified. Final wheel set c87cd8cc544c (130 wheels).
  - Probe on 9 fastapi tasks (`void/probe_inline_snapshot`, not used in results): 6 pass, 3 fail on test
    assertions with no import errors. Those 3 are left to the validity rule.
  - The partial 11-task run is voided (`void/..._NO_INLINE_SNAPSHOT`). The full validity checks restarted
    with wheel set c87cd8cc544c.

- **02:35 — RESULTS: E4B agentic localization on SWE-bench Lite (pre-registered 22:38; complete data).**
  - 900/900 episodes; the single infrastructure failure (django__django-11039/skill) was re-run once (manifest
    `agentloc_lite_e4b_s0_infra_retry`), giving a valid result. No exclusions.
  - Files: `agentloc_lite_e4b_s0.jsonl`, `_report.md`, `_exploratory.md`.
  - Function hit: base 20.7%, skill 32.0%, inject 30.0%.
  - **H7a confirmed:** inject vs base +9.3 pts [+4.3, +14.3] (repo-clustered [+2.7, +13.1]); 44 vs 16
    discordant, exact McNemar p = 0.0004.
  - **H7b confirmed:** skill vs base +11.3 pts [+6.3, +16.7] (clustered [+2.2, +14.9]); 52 vs 18,
    p = 0.0001.
  - **H7c confirmed:** inject uses −15,522 prompt tokens per episode [−19,437, −11,510] (clustered
    [−19,026, −12,056]); medians 33.7K → 19.9K. Skill: −11,830.
  - **Exploratory (not pre-registered):**
    - agents submit ~1 location (mean 0.97–1.07);
    - at the same number of locations, the agent given the ranking beats spanloc alone (skill 33.1% vs 22.8%,
      55 vs 25 discordant; inject 31.0% vs 23.8%), so the model adds precision on top of the localizer;
    - spanloc's own Hit@5 is 46.6%, so recall is left unused.

- **02:36 — correction:** `agentloc.report` took the upper middle element as the "median" for even n.
  It now uses the true median, matching the figures. Corrected medians of prompt tokens: base 33,080, skill
  20,856, inject 19,803 (the entry above said 33.7K → 19.9K). The paired mean differences (H7c) are unchanged.

- **02:47 — environment v3: repairs scoped per repository, declared dependency ranges respected (before any
  fix-experiment agent run).**
  - **Reference-patch check, wheel set c87cd8cc544c: 46/129 pass** (rich 30/48, fastapi 13/67, requests
    3/13, httpx 0/1). Two problems in that environment:
    - **Repair side effect.** inline-snapshot (added for fastapi) is a pytest plugin that imports rich at
      startup, so rich's tests ran against the installed rich 15.0.0, not `/workspace`. 8 rich tasks that
      passed in the original environment now fail; the only tracebacks through `site-packages/rich` are
      from this environment. All rich results in it are therefore suspect.
    - **starlette.** The harness keeps the highest version per distribution (swegemma 0.2.11
      `_deduplicate_wheels`), always starlette 1.6.0. 57 of 67 fastapi checkouts declare
      `starlette>=0.40.0,<0.47…<1.0.0`. 40 fastapi failures are `Router.__init__() got an unexpected keyword
      argument 'on_startup'` (removed in starlette 1.0).
  - The empty-patch stage of that run was stopped after 0 tasks (manifest `validity_empty_repaired`,
    status aborted). Wheel set c87cd8cc544c is superseded; its results are not used.
  - **Environment v3 (`scripts/build_envs.py`, record `experiments/05_find_vs_fix/envs.json`):**
    - Each added wheel goes only to the repository whose own logs showed the missing module. fastapi gets
      typing-inspection, dirty-equals, inline-snapshot, asttokens and executing; rich gets attrs; requests
      and httpx get the public wheel set unchanged.
    - For each package a checkout declares in `[project].dependencies`, wheels outside the declared range are
      left out when the newest one violates it. The harness's own rule then installs the newest allowed
      version, which is what pip would install. Only starlette is affected: 0.50.0 (38 tasks), 0.52.1 (7),
      0.48.0 (6), 0.49.3 (5), 0.47.3 (1).
    - 8 environments, one directory each (`data/envs/<sha256 of wheel list>`), with their own swegemma cache.
  - **Validity checks v3 (`scripts/run_validity_checks_v3.sh`):** per environment, the reference patch on all
    its tasks; then the empty patch on the tasks whose reference passed. Same rule: a task is valid iff its
    reference patch passes **and** its empty patch fails. Remaining causes (e.g. requests needs the
    `pytest-httpbin` fixture; fastapi_14962 needs the `ujson` C extension; rich_4070 expects older Pygments
    colours) are left to the rule, with no further repairs.
  - The fix experiment runs each task in its v3 environment, identically for all conditions.
- **02:51 — known quirk, no effect on results.** `locbench/competition.py` strips member names with
  `lstrip("./")`, which also drops the leading dot of `.github/…` paths. No gold patch among the 129 tasks
  touches a dot-path, so gold extraction and every reported number are unaffected. Frozen code
  (spanloc v0.2, the competition run) is left as it was.
- **02:58 — fix experiment: pilot and run plan (before any fix-experiment agent run).**
  - **Pilot:** 4 valid tasks, `random.Random(0).sample(sorted(valid), 4)`, all four conditions at once
    (`scripts/run_fix_all_conditions.sh e4b 2 <ids>`), 2 tasks at a time per condition. Results go to
    `fix_e4b_<cond>_pilot` and are **not** used in the analysis. Purpose: end-to-end check, time per task,
    GPU cost.
  - **Full run:** all valid tasks, the four conditions at once, so every condition sees the same endpoint
    load (the 10-minute budget is wall-clock time). 2 tasks at a time per condition (8 concurrent episodes,
    one L4), unless the pilot shows load problems (command timeouts or Docker memory errors), in which case 1
    per condition.
  - **Infrastructure failures** (endpoint errors matched by `INFRA_RE` in `locbench/fix_report.py`) are re-run
    once into a separate `_retry` folder, and the analysis uses the retry row. No other reruns.
  - **Models:** E4B; then 12B only if the projected total stays under the $20 plan (`experiments/BUDGET.md`).
- **03:00 — 12B endpoint smoke test** (`experiments/provenance/modal_smoke_test_12b_2026-10-23.txt`): first
  start of the 12B server, ready after 220 s; unauthenticated request → 401; tool call and thinking work.
  Single-stream decode ≈ 27 tok/s (388 tokens in 14.5 s) vs ≈ 52 tok/s for E4B (512 in 9.8 s,
  2026-10-22 smoke test). Under the same 10-minute wall-clock budget, 12B episodes get about half the tokens.
- **03:03 — serving note.** Modal web endpoints (including `web_server`) cap one HTTP request at 150 s and
  answer a longer one with a 303 redirect to a result URL (modal.com/docs/guide/webhook-timeouts). The
  harness's LiteLLM clients set `follow_redirects=True` (litellm `llms/openai/common_utils.py`), and the
  redirect stays on the same host, so long thinking completions are retrieved transparently. The pilot checks
  this empirically.
- **03:45 — RESULT: validity checks v3 complete. 86/129 tasks are valid** (`valid_task_ids.txt`,
  `valid_tasks_summary.md`; manifests `validity_v3_*`).
  - Per repository: rich 38/48, fastapi 48/67, requests 0/13, httpx 0/1.
  - Reference passes in 92 tasks; in 6 of them the empty patch passes too (requests 3, rich 1, fastapi 2),
    so they are excluded. requests: its tests import the installed release (src layout), so a reference
    pass says nothing about `/workspace`.
  - The starlette rule recovered fastapi: 43/57 pinned tasks now pass their reference patch vs 6/57 under
    starlette 1.6.0.
  - 13 valid tasks (fastapi 8, rich 5) have no function-level gold (module-level edits or new files), so
    their oracle_func text equals oracle_file.
  - **Pilot tasks** (rule of 02:58, `random.Random(0).sample(sorted(valid), 4)`): rich_2943, rich_3061,
    fastapi_14099, fastapi_14873.
- **03:50 — budget flags (before any fix-experiment agent run).** `swegemma eval` 0.2.11 never reads the
  submission's `eval_config.yaml` (only the scorer's inference stage does). Its own defaults are 60 minutes,
  unlimited tool calls and turns, and 300 s per command. `scripts/run_fix_experiment.sh` therefore reads the
  pre-registered budget from `eval_config.yaml` and passes it as flags: `--max-time-minutes 10
  --max-tool-calls 30 --max-turns 60 --timeout-seconds 120`. The verification timeout stays at the default
  300 s. The budget is recorded in each run manifest's note.
- **03:56 — pilot attempt 1 void: harness environment bug, fixed before any usable agent run.**
  - All 7 finished episodes failed before the first model call: `litellm.APIConnectionError … cannot import
    name 'CacheableResult' from 'mcp.types'` (then `acompletion_with_mcp`), after 5 LiteLLM retries.
  - Cause: swegemma 0.2.11 requires `litellm>=1.0.0` unpinned, so the harness venv had litellm 1.106.2, whose
    MCP code needs mcp>=2.2. google-adk 1.36.1 requires `mcp<2` and pins `litellm>=1.83.7,<=1.83.14` in its
    `extensions` extra.
  - Fix: litellm 1.83.14 (the newest google-adk allows) and transformers 5.13.1 (the scorer's serving
    version; litellm 1.83.14 pins tokenizers 0.22.2, which transformers 5.20 rejects). `uv pip check`: all
    compatible. Freeze: `experiments/provenance/env_venv-harness_2026-10-23_litellm-1.83.14.txt`.
  - Earlier results are unaffected: the validity checks make no model calls, and the find run used its own
    client in `.venv`.
  - Results moved to `void/pilot_attempt1_LITELLM_IMPORT`; manifests renamed `*_pilot_attempt1_void`. The
    pilot is rerun on the same 4 tasks.
- **04:22 — pilot (attempt 2) complete; operational checks only, outcomes not used.**
  - 16/16 episodes ran end to end (03:57–04:13): hints reach the model, patches are verified, 2 resolved.
  - Episode wall time (setup + agent + verification): median 194 s, max 518 s. Means: base 292 s
    (13.8 tool calls), spanloc 223 s, oracle_file 176 s, oracle_func 153 s.
  - **Load check (rule of 02:58): no problems.** No command timeouts (all 8 `CommandError`s are failing test
    runs or empty greps), no out-of-memory kills, no infrastructure errors. Two `404` read errors are the
    harness reporting a missing file through Docker's archive API. **Full run: 2 tasks at a time per
    condition.**
  - **Context overflow:** 3/16 episodes ended with `ContextWindowExceededError` (prompt > 24,576 tokens +
    8,192 output tokens > 32,768). This is the competition's 32K window, so it counts as a failure. It is not
    an infrastructure error (`INFRA_RE` does not match). Overflow per condition will be reported as an
    **exploratory** secondary outcome (not pre-registered).
  - **Long model calls:** the longest pilot call took 144.5 s. A 304 s completion (16,000 tokens) succeeded
    through LiteLLM, so Modal's 303 redirect is followed transparently
    (`experiments/provenance/modal_redirect_test_e4b_2026-10-23.txt`).
  - **Projection:** with 2 per condition, the base condition paces the run: ~86/2 × 292 s × 1.15 ≈ 4 h of
    endpoint time ≈ $3.7 (L4 + CPU + memory).
- **04:22 — full E4B fix run started** (`scripts/run_fix_all_conditions.sh e4b 2`; 86 tasks × 4 conditions).
- **05:00 — exploratory analyses declared before the E4B data is complete** (only the 4-task pilot has been
  seen; nothing here changes the pre-registered H8a–d tests):
  - **find × fix decomposition** per condition: P(final patch edits a gold function), and P(resolved | it
    does) vs P(resolved | it does not). The same at file level;
  - context overflow and empty-patch rates per condition;
  - per-repository breakdown (fastapi, rich);
  - tool calls and episode time per condition.
- **06:56 — E4B fix run complete: 344/344 episodes (86 per condition), 0 infrastructure errors, so no retry run.**
  Manifests `fix_e4b_{base,spanloc,oracle_file,oracle_func}` finished (04:22–06:56). Analysis follows in a
  separate entry.
- **06:56 — 12B launched (rule of 02:58: projected total < $20).** Spend: $4.38 of credit to 04:59 plus ~$1.9 for
  05:00–07:00 ≈ $6.3. 12B estimate ≈ $5 (about 5 h at ~$0.93/h; decode about half E4B's speed, episodes capped at
  10 minutes) → ≈ $11.3. Same agent, tasks, conditions and concurrency (`scripts/run_fix_all_conditions.sh 12b 2`).
- **06:58 — RESULTS: find vs fix, Gemma 4 E4B (pre-registered 23:52; complete data, 86 paired tasks).**
  Files: `experiments/05_find_vs_fix/fix_e4b_report.md`, `fix_e4b_summary.json`.
  - Resolved: base 11/86 (12.8%), spanloc 10/86 (11.6%), oracle_file 14/86 (16.3%), oracle_func 20/86 (23.3%).
  - **H8a confirmed:** oracle_func vs base +10.5 pts [+3.5, +17.4]; 10 vs 1 discordant, exact McNemar p = 0.012.
  - **H8b not confirmed:** oracle_file vs base +3.5 [−3.5, +10.5]; 7 vs 4, p = 0.55.
  - **H8c not confirmed:** spanloc vs base −1.2 [−7.0, +4.7]; 3 vs 4, p = 1.0.
  - **H8d confirmed:** oracle_func vs spanloc +11.6 [+4.7, +19.8]; 11 vs 1, p = 0.006. Here the realistic
    localizer recovers none of the gold-function gain.
  - Uncorrected, four comparisons per model, as pre-registered. **Repo-clustered intervals are uninformative
    with 2 repositories** (resampling 2 clusters gives 3 distinct means). They are not used; task-level
    intervals and exact McNemar are reported.
  - **Exploratory (declared 05:00):**
    - final patch edits a gold function (73 tasks with function gold): base 24, spanloc 35, oracle_file 41,
      oracle_func 68;
    - P(resolved | it does): 9/24 (38%), 10/35 (29%), 12/41 (29%), 19/68 (28%). P(resolved | it does not):
      1/49, 0/38, 1/32, 0/5;
    - so resolution ≈ P(reach a gold function) × ~30%. The hints move the first factor, not the second;
    - context overflow: 10%, 8%, 13%, 1%; empty patch: 12%, 5%, 8%, 0%; mean tool calls: 9.2, 8.2, 7.6, 6.1;
    - by repository (resolved): rich 5/3/6/7 of 38; fastapi 6/7/8/13 of 48.
  - **Post hoc, descriptive (computed after the results):** spanloc's top-8, the ranking the spanloc
    condition shows, contains a gold function in 36/73 valid tasks with function gold (49.3%) and a gold file in
    50/86 (58.1%), from `02_competition_localization/results.jsonl`. With the ranking, the agent's final patch
    reaches a gold function in 35/73 (48%), about as often as the ranking offers one. Resolution still does not
    rise.
- **07:15 — 12B on one L4 stopped (time-starved); rerun on one A100-40GB.**
  - The L4 run (06:56–07:12) finished 8 episodes. 7 hit the 10-minute cap with no patch (median 618 s). E4B on
    the same L4 never hit the cap (0/344, median 178 s).
  - On one L4 at 8 concurrent episodes, 12B's decode (27 tok/s single stream) is too slow for its thinking
    turns. That would give a floor effect and an uninformative comparison.
  - The decision uses timing only. No condition comparison was looked at; 7 of the 8 episodes had no patch.
  - **Rerun on one A100-40GB** (`serve_12b_a100`, $0.000583/s = $2.10/h). It has ~5x the L4's memory bandwidth,
    closer to the scorer's 4xL4 per stream. Image, weights, vLLM flags, agent, tasks and concurrency are unchanged.
  - Smoke test (`provenance/modal_smoke_test_12b-a100_2026-10-23.txt`): ready in 156 s; 392 tokens in 5.0 s
    (~78 tok/s single stream vs 27 on the L4).
  - The 8 L4 episodes are void (`void/fix_12b_L4_attempt_TIME_STARVED`, manifests `fix_12b_*_L4_void`).
  - **Budget:** ~$6.9 spent including this attempt. 12B on the A100 ≈ 3–3.5 h ≈ $8, total ≈ $15. E2B on L4
    afterwards ≈ $2.5, total ≈ $17.5 < $20.
  - **Paper:** report the hardware per model. Within-model comparisons share one endpoint and its load.
- **07:24 — 12B on the A100 (operational check, first 8 episodes, mixed conditions):** episodes finish in
  103–313 s, with no cap hits. 7 of 8 end in `ContextWindowExceededError` after 18–22 tool calls (E4B averaged
  6–9). The harness still verifies the diff left in the workspace (3 of these 8 have patches), so overflow is
  not automatically a failure. It is the official configuration's 32K window and applies to every condition.
  **The run continues unchanged.** Overflow per condition is part of the exploratory outcomes declared at 05:00.
- **07:35 — post hoc (E4B, after the results; descriptive only):** why spanloc raises gold-function edits but
  not resolution. Of the 73 tasks with function gold:
  - both base and spanloc reach a gold function in 21 (resolved: base 8, spanloc 6);
  - only spanloc reaches one in 14 (spanloc resolves 4; with the gold-function hint the same 14 give 5);
  - only base in 3 (base resolves 1).
  So spanloc's extra finds convert at about the oracle's rate. On common finds it resolves 2 fewer. Net 10 vs 11.
  The counts are too small to separate a real cost of the ranking from noise.
- **08:30 — E2B smoke test waiting for capacity:** its L4 container has been `Pending` since 08:18 (Modal had
  no L4 free; `modal container list`). The 12B A100 container is unaffected. E2B is needed only after 12B
  (~10:50), so it is retried then.
- **08:29 — E2B smoke test passed** (`provenance/modal_smoke_test_e2b_2026-10-23.txt`): ready after 630 s, mostly
  waiting for an L4; unauthenticated → 401; tool call and thinking work. 432 tokens in 5.2 s (~83 tok/s single
  stream on the L4, vs E4B 52). E2B will run on the L4 like E4B.
- **11:24 — 12B fix run complete (A100-40GB, 07:16–11:24): 344/344 episodes, 0 infrastructure errors, so no
  retry run.** Manifests `fix_12b_*` finished. Analysis in a separate entry.
- **11:24 — E2B launched on the L4** (rule of 02:58; `experiments/BUDGET.md`): $15.24 of credit used to 10:59,
  ≈ $16.1 after 12B, and E2B ≈ $2.0–2.3, giving ≈ $18.3 < $20. Guard: if the pace after its first hour projects past
  $20, stop and log. Same agent, tasks, conditions and concurrency (`scripts/run_fix_all_conditions.sh e2b 2`).
- **11:27 — RESULTS: find vs fix, Gemma 4 12B on one A100-40GB (pre-registered 23:52; complete data, 86
  paired tasks).** Files: `fix_12b_report.md`, `fix_12b_summary.json`.
  - Resolved: base 15/86 (17.4%), spanloc 19/86 (22.1%), oracle_file 18/86 (20.9%), oracle_func 23/86 (26.7%).
  - **H8a not confirmed** by the pre-registered test: +9.3 pts [+1.2, +18.6]; 12 vs 4 discordant, exact McNemar
    p = 0.077. The bootstrap interval excludes 0, and the direction matches E4B.
  - **H8b not confirmed:** +3.5 [−4.7, +11.6]; 8 vs 5, p = 0.58.
  - **H8c not confirmed:** +4.7 [−3.5, +12.8]; 9 vs 5, p = 0.42.
  - **H8d not confirmed:** +4.7 [−4.7, +15.1]; 12 vs 8, p = 0.50.
  - Repo-clustered intervals are uninformative (2 repositories); not used.
  - **Exploratory (declared 05:00):**
    - P(resolved | final patch edits a gold function): 13/20 (65%), 17/24 (71%), 16/27 (59%), 22/39 (56%).
      E4B: 28–38%;
    - the patch edits a gold function in 20, 24, 27, 39 of 73 tasks. Even with the gold function named, only
      39/73 (E4B: 68/73);
    - context overflow 66%, 66%, 64%, 53%; empty patch 52%, 47%, 47%, 44%; mean tool calls 18.0, 17.5, 16.6,
      16.1 (E4B 6–9);
    - so 12B fixes well once it edits the right function but often never gets there inside the 32K window. E4B
      gets there (with the hint) but often fails to fix;
    - by repository (resolved): rich 6/9/8/11 of 38; fastapi 9/10/10/12 of 48.
- **12:40 — E2B cost guard (one hour after its first episodes; pace and cost only):**
  - Done: base 27/86, spanloc 36, oracle_file 35, oracle_func 38. Episode mean 262 s for base, 177–200 s for
    the others.
  - Base paces the run: ETA ~14:50, the others ~14:05.
  - Projection: ~$16.3 spent through 12B's tail; the L4 from ~11:35 to ~14:56 adds ≈ $3.1, giving ≈ $19.4 < $20.
    **E2B continues.**
  - L4 allocation took ~15 min (episodes began 11:40). A pending container is not billed.
- **14:30 — RESULTS: find vs fix, Gemma 4 E2B on one L4 (pre-registered 23:52; complete data, 344/344 episodes
  11:40–14:27, 0 infrastructure errors, 86 paired tasks).** Files: `fix_e2b_report.md`, `fix_e2b_summary.json`.
  - Resolved: base 3/86 (3.5%), spanloc 7/86 (8.1%), oracle_file 8/86 (9.3%), oracle_func 13/86 (15.1%).
  - **H8a confirmed:** +11.6 pts [+5.8, +18.6]; 10 vs 0 discordant, exact McNemar p = 0.002.
  - **H8b not confirmed:** +5.8 [+1.2, +11.6]; 5 vs 0, p = 0.063.
  - **H8c not confirmed:** +4.7 [+1.2, +9.3]; 4 vs 0, p = 0.125.
  - **H8d confirmed:** +7.0 [+2.3, +12.8]; 6 vs 0, p = 0.031.
  - **Exploratory (declared 05:00):**
    - final patch edits a gold function: 23, 25, 34, 60 of 73. P(resolved | it does): 3/23 (13%), 6/25 (24%),
      6/34 (18%), 12/60 (20%);
    - context overflow 29%, 10%, 15%, 2%; empty patch 35%, 16%, 26%, 12%; mean tool calls 7.9, 7.0, 6.2, 5.4;
    - by repository (resolved): rich 1/3/4/6 of 38; fastapi 2/4/4/7 of 48.
  - **Across the three models (exploratory):**
    - P(resolved | the patch edits a gold function) rises with size: E2B 13–24%, E4B 28–38%, 12B 56–71%;
    - P(the patch edits a gold function | the gold function is named): E2B 82%, E4B 93%, 12B 53%. 12B keeps
      exploring and overflows its context.
    - Gold function vs base is positive for all three: +11.6 (p = 0.002), +10.5 (0.012), +9.3 (0.077).
- **15:03 — all GPU work done.** Modal billing (complete hours to 14:59): $18.84 metered (A100-40GB $8.96, L4
  $8.09, CPU $1.25, memory $0.51); $18.85 of the $30 credit used, $0.00 billed; no containers running. Within the
  $20 plan. Ledger: `experiments/BUDGET.md`.

### Pre-registration: context management for 12B (20:54, before any variant episode)

- **Why:** 12B fixes 56–71% of tasks once its patch is in a gold function (exploratory, LOG 11:27), but it
  outgrows the 32K window in 53–66% of episodes. Even with the gold function named, it edits it in only 53% of
  tasks. Retained thoughts (`include_thoughts: true`, the official sample setting) are a large part of that context.
- **Intervention:** `include_thoughts: false`, a harness-supported setting. Reasoning stays on each turn (thinking
  budget 4,096), and earlier thoughts are removed from the history (`adk_submission/resolvers/generation.py`).
  Everything else is unchanged: agent, prompt, the 86 valid tasks, budgets, the 12B W4A16 checkpoint, the A100-40GB
  endpoint `serve_12b_a100`, image and weights. GPU on Modal only; the Mac runs only the Docker sandboxes.
- **Conditions:** `base_nothoughts` and `oracle_func_nothoughts`, 4 tasks at a time each (8 concurrent episodes,
  the same load as the original 12B run). `scripts/run_fix_all_conditions.sh` with `CONDS="base oracle_func"
  VARIANT=nothoughts SERVE_KEY=12b-a100`, concurrency 4.
- **Controls:** the original 12B `base` and `oracle_func` runs (07:16–11:24; same endpoint, same load), paired by
  task. The controls are not concurrent; stated as a limitation.
- **Hypotheses** (exact McNemar on paired tasks, task-level bootstrap CI; 2 comparisons, uncorrected):
  - H9a: `base_nothoughts` resolves more tasks than `base`;
  - H9b: `oracle_func_nothoughts` resolves more tasks than `oracle_func`.
- **Manipulation check** (reported regardless): context overflow is lower in both conditions. If it does not
  fall, H9 cannot be interpreted.
- **Secondary (exploratory):** empty patches, tool calls, time-cap hits, P(final patch edits a gold function),
  P(resolved | it does); within the variant, oracle_func vs base.
- **Infrastructure failures** are re-run once into `_retry` (rule of 02:58). Analysis: `locbench/context_report.py`.
- **Budget:** estimate ≈ $5 (172 episodes on the A100). Guard: stop if the projected spend for this run exceeds
  $7 (total ≈ $26 of the $30 credit).
- **21:03 — credit guard:** pause all GPU work when the $30 Modal credit runs out.
  `scripts/credit_guard.sh` (nohup, pid 43301) checks `modal billing summary` every 5 minutes. At $27.50 of credit
  used (margin for up to an hour of billing lag) or any billed amount, it:
  - kills all runners and removes the sandboxes;
  - stops the Modal app;
  - writes `experiments/costs/CREDIT_GUARD_TRIPPED`, which blocks new runs in `scripts/run_fix_experiment.sh`.
  Log: `experiments/costs/credit_guard.log`. Credit used at start: $19.19.
- **21:10 — context experiment stopped by its budget guard (pre-registered 20:54); H9a/H9b not tested.**
  - After 8 finished episodes (4 per condition, rich tasks), 5 had hit the 10-minute cap. The original 12B run
    had 0 of 344.
  - First trace (rich_4076): 8,765 completion tokens vs 2,931 in the original episode. Summed prompt tokens fell
    only 9% (221,681 vs 244,644).
  - Context overflow on the 8 paired tasks: 2 vs 3 in the original run (exploratory, tiny n).
  - Without its earlier thoughts, 12B re-thinks on every turn: turns get slower and episodes hit the time cap
    instead of overflowing. In the original runs, 12B's retained thoughts were short (median 178 characters per
    agent message), so its context fills mainly with tool output.
  - At ~50 episodes/h the run projected ≈ $8 > $7. Stopped, sandboxes removed. Manifests
    `fix_12b_*_nothoughts`: status "stopped (budget guard)". The data stay as an exploratory observation only.
  - **Implication (exploratory):** `include_thoughts: false` trades the context bottleneck for a time
    bottleneck. A better-targeted intervention would cut tool-output context or per-turn thinking (for example a
    lower `thinking_budget`). That would need a new pre-registration and budget.
- **21:39 — decision: test the hypothesis, spending up to the full $30 credit if needed.**
  - Credit guard restarted at $29.50 (pid 48543). It still trips on any billed amount; the hard limit is the $30
    credit. Credit used at restart: $19.59.
  - The run's own $7 guard is replaced by the credit guard. Projection ≈ $8, so the total is ≈ $28.
  - The partial run (8 episodes, stopped 21:10) is set aside unanalysed (`void/fix_12b_nothoughts_partial_stopped_2110`,
    manifests `*_partial_stopped`). Its resolved outcomes were never looked at.
  - The pre-registered design of 20:54 is unchanged and is re-run from scratch on all 86 tasks per condition, with
    the same load (8 concurrent episodes) and the same endpoint.
  - If the credit guard trips first, the analysis uses the tasks completed in both conditions (same task order),
    labelled as incomplete.
- **00:52 (2026-10-24) — RESULTS: context management for 12B (pre-registered 20:54; complete data: 172/172
  episodes 21:41–00:51, 0 infrastructure errors).** Files: `context_12b_nothoughts_report.md`,
  `context_12b_nothoughts_summary.json`.
  - **H9a not confirmed:** base, nothoughts vs original 15/86 vs 15/86, +0.0 pts [−9.3, +8.1]; 7 vs 7 discordant,
    exact McNemar p = 1.0.
  - **H9b not confirmed:** oracle_func 26/86 vs 23/86, +3.5 [−4.7, +11.6]; 8 vs 5, p = 0.58.
  - **Manipulation check holds:** context overflow fell (base 66% → 48%, oracle_func 53% → 36%).
  - **But the time cap took its place:** 10-minute cap hits base 8% → 19%, oracle_func 10% → 27%. Median episode
    3.7 → 6.7 min and 5.0 → 8.1 min.
  - Empty patches were unchanged (52% → 49%, 44% → 45%).
  - Reach / fix (exploratory): base 20/73 → 22/73 reach a gold function (fixed 13 → 12); oracle_func 39/73 →
    36/73 (fixed 22 → 24).
  - **Conclusion:** dropping earlier thoughts relieves the context bottleneck but moves 12B onto the 10-minute
    time cap, so resolution does not change. Relieving 12B needs less tool output in context or less thinking per
    turn, not less retained thought.
  - **Run-to-run noise (descriptive):** with identical overall rates, 14 of 86 base tasks changed outcome between
    the two runs. Single-run per-task comparisons are noisy, which supports the paired designs.
- **01:03 — all GPU work done (again).** Modal billing: $26.93 metered (A100-40GB $16.62, L4 $8.09); $26.94 of the
  $30 credit used, $0.00 billed; no containers running. The credit guard (threshold $29.50, pid 48543) stays on.

## 2026-11-02

- **00:39 — October billing closed** (`costs/billing_2026-10_final_*.summary.{json,txt}`, `modal billing summary
  --for 2026-10`): metered $28.13 = deployed apps $26.85 + ephemeral $0.04 + egress $0.04 + volumes $1.20. Credits
  used $26.89, billed $0.00; volumes are covered by free storage and egress by the allowance. This agrees with the
  paper's "$26.93 metered" (compute + egress, `paper/tables/compute.md`). November so far: $0.00.
- **00:40 — new Modal token** stored as profile `g4main` (`--no-activate`; active profile
  unchanged). It resolves to the **same `shetu` workspace** (the deployed `g4paper-vllm` app is visible), not a
  separate account. All scripts keep using `MODAL_PROFILE=shetu`.
- **00:41 — credit guard v2.** v1 (pid 48543) had been silent since 2026-11-01 06:00: in a month with no use, the
  text summary prints no "Credits:" line, so its parser found nothing (no GPU work ran meanwhile). v2
  (`scripts/credit_guard.sh`) parses `modal billing summary --json`, logs a warning when unreadable, and on trip
  stops every deployed app in the workspace (paper and Main Track). Threshold $29.50 month to date, every 300 s,
  pid 11424.
- **00:44 — paper figures:** Figure 1's end labels (71% / 72%) overlapped; series ending within 4 points now
  share one label ("71–72%"). All figures regenerated (`paper/make_figures.py`; no data change).
- **00:45 — paper text:** the writeup cited only Figures 1 and 4; "Figure 4" renamed "Figure 2" (two places).
  No other text change; 2,627 + 270 = 2,897 words.
- **PDF builds (no content changes):** `scripts/md_to_pdf.py` (Markdown → HTML → headless Chrome) and
  `paper/make_pdf.py` → `paper/pdf/finding-is-half-the-fix_draft_2026-11-02.pdf` (8 pages, Figures 1–2,
  numbered citations, draft note). Internal project report (15 pages, not part of
  this repository).
- **Readiness review (Paper Track):** research complete; joined on Kaggle (`kaggle competitions list` shows
  entered for both tracks). Still open:
  - a final edit pass of the writeup (`writeup.md` unchanged since 2026-10-24 01:03);
  - the code-release decision: no git repository or LICENSE yet; the notebook was built but never run and needs
    the source as a Kaggle dataset;
  - creating and submitting the Writeup.
  H5 (competition embeddings) was registered but never tested; the paper makes no claim about it.
- **Main Track started:** groundwork and plan in `../gemma-4-developer-agent/` (CPU only so
  far; no GPU spend).
- **~01:10 — validity caveat found while planning the Main Track: no context compaction in our fix runs.**
  - Harness README v3 §7.2 (`data/competition_repaired/HARNESS_README.md`): the scorer's App uses
    `EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336,
    event_retention_size=5)` and `ContextCacheConfig(2048, 1800 s, 10)`.
  - swegemma 0.2.11 `cli.py:245` builds `EvalConfig` without either. `harness/agent_runner.py:692-695` passes them
    to the App only if set. So every `swegemma eval` fix run (E2B, E4B, 12B, H9) ran **without compaction**.
  - **Unaffected:** the paired hint comparisons (H8a-d, H9), since both arms share the setting.
  - **Not scorer-faithful:** absolute overflow rates (12B 53-66%; E2B base 29%) and the 12B "fills its context"
    reading.
  - **Paper updated:** abstract (+"without the scorer's context compaction; §8"), the §5 "next lever" sentence and a
    new limitation bullet. Now 2,670 + 270 = 2,940 words. PDFs rebuilt.
  - **Optional follow-up** (not run; depends on November credit): 12B base + gold function with
    compaction on the A100, ≈ $8.

### Pre-registration: find vs. fix with oracle locations (23:52, before any competition data exists locally)

- **Tasks:** the 129 public competition tasks. Tasks whose **reference patch**
  fails our local verification (environment problems, cf. community reports
  of 43–127/129) are excluded *before* any agent run, by the rule "gold patch
  must pass".
- **Conditions:** `locbench/make_task_variants.py`. Text appended to the
  issue only:
  - base;
  - spanloc (top-8 ranking);
  - oracle_file;
  - oracle_func (gold functions with line ranges).
- **Agent:** the official harness (`swegemma eval` 0.2.11, Docker sandbox on
  the Mac), with one fixed agent config for all conditions. Model served
  by vLLM on Modal.
  - Budget per task: ≤ 30 tool calls, ≤ 10 min, thinking on with budget
    4096 (the harness default).
  - Models: E4B first; 12B, then E2B, as the GPU budget allows.
- **Primary outcome:** the official PASS/FAIL (validation tests pass).
- **Secondary outcomes:**
  - does the final patch touch a gold file / gold function;
  - tool calls; wall time.
- **Hypotheses:**
  - H8a: oracle_func > base;
  - H8b: oracle_file > base;
  - H8c: spanloc > base;
  - H8d: (oracle_func − base) > (spanloc − base), i.e. a realistic
    localizer recovers only part of the localization ceiling.
- **Tests:** exact McNemar per pair; paired bootstrap CIs. 4 pre-specified
  comparisons per model, reported without multiplicity correction and
  labelled as such.

### Pre-registered hypotheses (~12:50, before the tests below were run)

Status codes: *prelim* = partial evidence seen; *open* = not yet tested.

| # | Hypothesis | Test | Status |
|---|---|---|---|
| H1 | Ranking functions and aggregating to files beats whole-file BM25 at file level | Acc@1/Acc@5, paired bootstrap, Lite + competition | prelim (+12.7 Acc@1 on 134 Lite tasks) |
| H2 | Under a fixed token budget, reading ranked function spans reaches the gold function with fewer tokens than reading ranked whole files | budgeted success at B = 1K–16K; median tokens to first gold | open (budget metric implemented after this entry) |
| H3 | Graph propagation over the AST graph adds < 5 points function Acc@5 over BM25 + mentions | paired bootstrap | prelim (+3.1, n.s.) |
| H4 | Quoted code lines raise function Hit@1 on tasks whose issue quotes a source line | dev split, then Lite once | open |
| H5 | The competition embeddings, queried with the issue text, are weaker than function BM25 at function level | Acc@k, competition tasks | open |
| H6 | The competition graph and our AST graph agree on most nodes but differ in edges | node/edge overlap | open |
| H7 | With graphloc available, a Gemma 4 agent localizes more often and uses fewer tokens and turns | agentic localization, same tasks/seeds, McNemar + paired bootstrap | open |

### Results, frozen v0.1, SWE-bench Lite, all 300 tasks (13:08, from `date`)

Files: `experiments/03_swebench_generalization/{summary,budget}_lite_v01.{md,json}`.

- **H1 confirmed:** file Acc@1 54.7 (function BM25 aggregated to files) vs
  38.7 (whole-file BM25); Acc@5 76.3 vs 64.7.
- **H2 confirmed:** median tokens to the first gold function 3,447 (function
  BM25) vs 27,535 (whole files), 8.0× fewer; first-gold@4K 53.4% vs 12.1%.
  Reading only the gold spans needs a median of 410 tokens.
- **H3 confirmed (null):** graphloc minus BM25, function Acc@10 +1.7
  [−1.4, +4.8], Hit@1 −1.0 [−5.2, +3.1]. 81.5% of gold functions lie within
  2 hops of the BM25 top-10, but propagation does not rank them up.
- Path prior: removing it costs 7.3 points function Acc@10 (49.7 → 42.4).

Note on H2: the budget metric's first output (104 Lite tasks, ~12:52) came
*after* H2 was written; it showed median tokens to the first gold function of
2,366 (function BM25) vs 17,589 (whole-file BM25).

# BUILD_LOG: SharkNinja cross-retailer project

## [2026-09-23] Phase 0 — Data discovery and snapshot
**Built:**
- `DATA_SOURCES.md`: survey of official APIs, paid providers and free datasets.
- `data/raw/amazon2023/meta_sharkninja.jsonl` (2,012 listings: 1,169 Shark/Ninja brand store, 843 Amazon Renewed), streamed and filtered from the McAuley Lab Amazon Reviews 2023 Home & Kitchen + Appliances metadata (3.8M items).
- `data/raw/amazon2023/reviews_sharkninja.jsonl` (293,270 reviews, Aug 2002 to Sep 2023), filtered from the 67.4M-line Home & Kitchen review file.
- `data/raw/benchmarks/`: Walmart-Amazon, Abt-Buy, Amazon-Google (matchbench parquet), PriceRunner (lakritidis/product-matching), Octoparse workflow sample.
- `explore/snapshot.py` → `explore/data_snapshot.html`: per-dataset column profile (type, fill %, distinct, examples) and sample rows.
- `.venv` (Homebrew Python 3.14, pandas 3.0.6, pyarrow). The Anaconda install has a NumPy 1.x/2.x conflict.
**Tested:** snapshot script ran end to end on the full data; page opened in the browser pane and its text was read back to check every section rendered.
**Result:** pass
**Issues:** Kaggle datasets were not pulled (no Kaggle token). Dataset eras for the benchmarks are approximate. No license is stated for the Amazon 2023 dataset or the Magellan benchmarks.

## [2026-09-23] Phase 1 — Crosswalk and join-key audit
**Built:** `PLAN.md` (living plan with a shared column layout across all datasets); DuckDB added to `.venv`.
**Tested:** SQL checks in DuckDB. Reviews → listings join on parent_asin: 293,270 of 293,270. Shark/Ninja/Euro-Pro rows in every benchmark: 0. Walmart-Amazon model-number fill: 94% Walmart, 71% Amazon.
**Result:** pass
**Issues:** no product overlap between datasets, so cross-dataset alignment is by shared schema, not by join. Phase 2 pattern-discovery agents launched (SharkNinja data; benchmarks).

## [2026-09-23] Phase 2 — Pattern discovery (two Sonnet agents)
**Built:** `explore/patterns/amazon_sharkninja.md` + `_rules.py`; `explore/patterns/benchmarks.md` + `_rules.py` + `run_analysis.py`. PLAN.md updated with findings and the Phase 3 cleaning order.
**Tested:** orchestrator re-queried the key numbers in DuckDB. Walmart-Amazon: model-number match 76% of matches vs 0% of non-matches; brand equal in 73% of non-matches. SharkNinja: item model number filled for 1,353 of 2,012; LYTIO/Lutema only on Renewed; 76 listings with reviews before launch; Renewed → brand-store model-number link 145 exact / 163 base. All consistent with the agents.
**Result:** pass
**Issues:** the agent's ~94% model-number coverage from a bare-title regex is an estimate, not yet verified. The benchmark agent left `/tmp/_bench_results.json`; removed.

## [2026-09-23] Phase 3 — Cleaning
**Built:** `pipeline/rules.py`, `pipeline/clean.py` → `data/clean/` (sn_listing, sn_review, rejected_reviews, bench_listing, bench_pair, pricerunner_offer, cleaning_report.md).
**Tested:** full run on all data. Printed and read samples: 20 of 20 title-sourced models correct, 34 of 34 suffix-merge groups plausible, 15 of 15 refurbished → brand-store links the same product, and all 18 "unrelated" and 20 "unverified" listings reviewed by eye. Two rule bugs were found and fixed this way (short model codes dropped; genuine products without a brand word marked unrelated).
**Result:** pass
**Issues:** 20 listings stay "unverified" (including Fantom; Euro-Pro heritage not confirmed). model_no confidence is "low" for 46 multi-code titles. Price and launch date remain sparse; that is inherent to the source.

## [2026-09-23] Phase 4 — Entity resolution (in progress: held-out test pending)
**Built:** `pipeline/match.py` (layered deterministic scorer), `eval/bench_eval.py`, `pipeline/resolve_sn.py` (→ sn_listing_product, sn_product, sn_unmatched, resolution_report.md), `eval/sn_eval.py`, `eval/sample_pairs.py`. Rules added after error analysis: model containment, strict model-conflict, number-mismatch penalty (benchmark); unit core_model, position-based accessory detection, separate accessory ID namespace, no fuzzy matching for accessories, ASIN-shaped values rejected as models (SharkNinja).
**Tested:** Benchmarks (tuned on train+valid, scored on test): Walmart-Amazon P 0.870 / R 0.834 / F1 0.852 (model-only 0.787); Abt-Buy F1 0.847; Amazon-Google F1 0.503. SharkNinja dev set (145 blind-labelled pairs, used for tuning): pooled P 0.864 → 0.953, R 0.729 → 0.854. Accessory title rule: 0 errors on a 26-title fixed test list (a development list). Fresh held-out set of 123 pairs sampled and sent for blind labelling.
**Result:** pass. Held-out SharkNinja test (118 labelled pairs, never tuned on): precision 0.869, recall 0.914.
**Issues:** regex slip (ungrouped alternation) caught by the fixed title list before it reached data. Dev-set numbers are optimistic by construction. The two blind labelling runs disagree on single-letter suffix variants (S4701D, S3601D, AF100/AF101), so part of the held-out error is definitional. Remaining clear errors: an attachment linked to its blender; cookware bundles with different contents merged.

## [2026-09-23] Phase 4b — Manual suffix check and product-count sanity check
**Built:** title-explicit model override, `data/manual/model_aliases.csv` (AF100→AF101, NV482→NV480), self-empty product split (-SE), bundle products (SN-B-), extra accessory words, `eval/accessory_title_cases.py` (31-title regression list), `eval/sn_test_adjudications.csv`.
**Tested:** read full listing fields for WS642*, S4701*, S3601*, S3501*, AF100/101, EP033*, HV301/302; checked shared rating pools at 20/100/200/500 ratings; inspected the 6 largest product groups and 25 random unit singletons. Accessory regression list 0/31 errors. Held-out test unchanged by the fixes (P 0.869, R 0.914); with evidence-based adjudication P 0.948, R 0.917.
**Result:** pass
**Issues:** HV301/HV302 left unresolved (self-contradicting listing). 159 unit singletons remain, mostly refurbished listings with generic titles that fit several models.

## [2026-09-23] Phase 5 — Time panel
**Built:** `pipeline/panel.py` → sn_panel_month, sn_product_event, sn_product_summary, panel_report.md.
**Tested:** review totals reconcile exactly (289,376); 0 gaps in any monthly series; launch never later than first review (0 after the earliest-evidence fix; 96 before). AF101 spot check: launch Aug 2018, 2019 peak 2,087 reviews, avg 4.5–4.7. Found the crawl-tail drop after March 2023 and flagged it.
**Result:** pass
**Issues:** 90% brand-store linkage target not met (77%); written reviews are ~13% of star ratings (AF101), so volume is a proxy.

## [2026-09-23] Side quest — SharkNinja catalogue sources
**Built:** `explore/catalog_sources.md` (sandboxed Sonnet research agent: web search and page fetch only, one writable file).
**Tested:** orchestrator re-fetched ManualsLib: "more than 1417 Shark Vacuum Cleaner manuals", roughly 300–400 distinct models. Compared with our 378 vacuum products (312 keyed).
**Result:** pass (no complete official catalogue exists publicly; a rough cross-check does)
**Issues:** alias evidence is from search snippets only; the official support site did not render for fetch tooling.

## [2026-09-23] Phase 7 prep — Storyboard v1 and v2 (visual, no build)
**Built:** Design canvas "Demand Evidence Storyboard" (https://claude.ai/artifact/JnuBnJf8Wk93tZdqtumuBA), generated from real panel data by a scratchpad script. v1: 5 frames. v2 (owner feedback): footer with copyright → mohithgujjula.com and Method link on every frame; product dropdown (plus an open-dropdown frame); From/To window; checkboxes for new/refurbished; Volume/Rating toggle switch; monospace eyebrow text removed; "Take the tour" button plus a tour-step frame; Method and limits expanded to a full 9-section page.
**Tested:** generator checks: no small monospace meta text left on any frame, footer on every frame; all chart numbers come from the panel parquet. Not rendered or screenshotted by me.
**Result:** partial (awaiting owner visual review)
**Issues:** step 6 results are placeholders in square brackets.

## [2026-09-23] Phase 6 — Event tests with placebo calibration
**Built:** `pipeline/events.py` → sn_event_test, sn_event_band, sn_event_control, sn_event_pooled, events_report.md.
**Tested:** placebo (fake-date) checks after every design change. False-alarm rate among testable fake events: 21% (first design) → 7.5% (life-stage matching + calibrated range) → 10.4% with the broad-category tier (held-out set B). Benjamini-Hochberg q=0.10 on empirical p-values: 0 of 819 real events survive. Pooled effects re-estimated with a product-level cluster bootstrap. Manually inspected the top "moved" events and found duplicated same-month sibling events; merged.
**Result:** pass (method calibrated; the finding is that single events are not detectable in review data, averages are)
**Issues:** pooled effects are associations (halo or growth timing; returns volume for refurbished). Runtime ~6 min (placebo sets).

## [2026-09-23] Phase 7 + 8 — Front end and chat service (built locally, mock mode)
**Built:** `pipeline/export_web.py` → `web/data/` (portfolio, products, 1,133 per-product JSON, 9.9 MB). `web/` (vanilla HTML/CSS/JS, hash routing: Portfolio, Product, Event evidence, Findings, Method; searchable product combobox; From/To; channel checkboxes; Volume/Rating switch; 7-step guided tour incl. the assistant; chat drawer with suggested prompts, view chips with Undo). `app/` (Flask; 7 read-only tools over DuckDB; Haiku 4.5 tool loop with prompt caching; mock LLM; per-visitor rate limit; daily $ ledger; optional Turnstile/invite code; 17 real-model test cases + runner, not run). Specs: `docs/SPEC_frontend.md`, `docs/SPEC_backend.md`. Built by two Sonnet builder agents; orchestrator reviewed, fixed and verified.
**Tested:** `pytest app/tests` 63 passed (orchestrator re-ran). Mock chat end to end in the browser: "Show AF101 from Jan 2019 to Dec 2020, new units only" set the view, redrew the chart, showed the Undo chip. Visual QA at 1440×900 on every page, tour steps, chat drawer; 375 px has no horizontal scroll. Found and fixed: charts overflowing their cards, overlapping event labels, raw launch-source codes, clipped selects, an event headline contradicting its verdict, question-style headings, pill-shaped prompts, em dashes, hyphen minus signs; tool bugs: exact-match product types ("air fryers" returned nothing) and refurbished share dominated by refurbished-only products; server port 5000 clashes with macOS AirPlay (now PORT, default 5055).
**Result:** pass (local, mock mode)
**Issues:** real-model behaviour untested until the key arrives (17 cases ready). Hallmark CLI not installed, so its 65-gate audit was not run. Not deployed.

## [2026-09-23] Deploy 1 — Static page live at mohithgujjula.com/work/demand-evidence/
**Built:** staged `web/` to jarvis:~/de-deploy/ (own folder), owner ran the sudo rsync + chown into /var/www/mohithgujjula/work/demand-evidence/. No nginx change needed (existing try_files serves it). Chat intentionally offline until the Haiku test run. Owner also removed the publicly served /.claude/launch.json (flagged in passing).
**Tested:** pre-deploy capacity check (11 GiB available, disk 48%, load 0.98/12). Live: all assets and data return 200; /.claude/launch.json now 404; browser check of Product, Portfolio, Findings, Method, Event and NV360 pages with real headlines; chat drawer shows the offline message; only console error is the expected 404 from api/chat. Portfolio headline "9.4× from 2013 to 2022" verified against the data (4,323 → 40,835).
**Result:** pass
**Issues:** chat service not deployed yet (needs key + real-model test + one sudo session for systemd and an nginx /work/demand-evidence/api/ proxy route with a rate limit).

## [2026-09-23] Deploy 2 — Moved to apps.mohithgujjula.com, open-sourced, Work entry
**Built:** app at https://apps.mohithgujjula.com/demand-evidence/ (static, ~/apps-landing, no sudo); card on the apps landing page; public repo https://github.com/auto-mo/demand-evidence (MIT; 78 files; two commits via the GitHub API because Apple git is blocked by the unaccepted Xcode licence); Work entry on mohithgujjula.com (staged, needs owner sudo). Fixes found while doing it: router focus scrolled every page 64px under the sticky header; Cloudflare caches JS/CSS/JSON for 4h, so `scripts/stamp_version.py` stamps one version onto every module, stylesheet and data URL; owner feedback applied (Volume/Rating switch now two equal options with an arrow knob, refurbished colour #8DBBF0 for contrast with graphite, no thick rounded focus ring on chart bars); "X, not Y" copy and remaining &mdash; entities rewritten; `?notour` URL switch.
**Tested:** publish check: no tokens/keys, no private IPs; data (no redistribution licence), listing-text samples, dev folders and hard-coded paths excluded or fixed. Live checks with curl and the browser; headless screenshots viewed before use; GitHub reports MIT; apps landing shows the card.
**Result:** pass (Work page deploy pending owner sudo)
**Issues:** chat still offline pending the Haiku test run.

## [2026-09-23] Phase 8b — Real-model testing on Haiku 4.5, and deploy staging
**Built:** fixes from the real runs: tool schemas (strict mode rejected: range keywords, then "schema too complex"; strict removed, server-side clamps already in place, test guards the schema); timeline tool totals now from the full range (a shared 72-row cap had cut AF101's refurbished total from 10 to 4, and the model repeated it); event tool returns a deterministic plain_summary and clearer field names (the model had called +21.9% vs comparison "a 21.9% decline"); prompt rules for ambiguous products and unrequested view changes; em dashes stripped from replies in code; `measure` aligned to the page contract (volume | rating); runner fails on API errors (the first run's 5 "passes" were fallback text) and gained --only. Staged on jarvis: ~/demand-evidence (code, 6 parquet files, venv with pinned Flask/anthropic/duckdb/python-dotenv + gunicorn 26.2.0, .env mode 600) and deploy/ (systemd unit with MemoryMax 512M / CPUQuota 50%, nginx limit_req zone keyed on CF-Connecting-IP, /demand-evidence/api/ route, install.sh with automatic rollback if nginx -t fails).
**Tested:** real runs: 0/17 (API 400, $0) → 14/17 ($0.137) → 14/17 ($0.140) → final 5 changed + regression cases 5/5 ($0.043); all 17 cases now pass. Total real-API spend ≈ $0.32 plus a $0.013 smoke test on jarvis (gunicorn started by hand, health + one real chat that set the view correctly, stopped by exact PID). pytest 65 passed.
**Result:** pass (service install awaits owner sudo)
**Issues:** prompt caching does not engage (the ~2.4k-token prefix is below the model's minimum cacheable size); cost per question measured at about $0.003 to $0.02.

## [2026-09-23] Deploy 3 — Assistant live
**Built:** owner ran deploy/install.sh: systemd `demand-evidence` (gunicorn 1 worker × 4 threads on 127.0.0.1:5021, MemoryMax 512M, CPUQuota 50%), nginx /demand-evidence/api/ route with a per-visitor limit_req zone keyed on CF-Connecting-IP; Work entry re-published without the "switches on after its test run" note. Chat now renders light markdown (**bold**, bullet and numbered lists) with DOM text nodes only.
**Tested:** service active with the limits applied; health through the public URL; a real question through the public route; in the live page, "Show AF101 from Jan 2019 to Dec 2020, new units only" set From/To, unticked Refurbished and showed the "Set:" chip; a list reply renders without literal asterisks or em dashes.
**Result:** pass
**Issues:** none open. Turnstile not configured (optional); the daily cap and per-visitor limits are active.

## [2026-09-24] Round 3 — Intro carousel, cases, sortable portfolio, real rating mode
**Built:** 5-card intro carousel (what it is, the data, the source, what it can show, what it cannot) before a trimmed 5-step tour; default product SN-HV322 (2,457 new / 278 refurbished reviews, 14 tested events of all three kinds); Volume/Rating switch now changes the main chart (rating lines, volume strip underneath); legend window totals and a "too few to see" note for refurbished under 2%; plain subject lines stating the data is written Amazon reviews; portfolio chart from 2010 with a note that 2002-2009 hold 1,569 reviews; sortable family table with a heading that follows the sort (refurbished share ranks families with >= 50 new-unit reviews first); "Cases worth a closer look" on Findings (largest drops/rises per event type; drops after a sibling launch labelled possible cannibalisation); chart marks tested events only; untested events collapsed in the rail; tour icon dot; `find_cases` tool for the assistant (+ prompt rule, 2 tests, 1 real-model case). Front end by the Sonnet builder; data export, tool and fixes by the orchestrator.
**Tested:** pytest 67 passed; real-model case find-cannibalisation-cases passed ($0.009); live checks: carousel opens first on a fresh visit, default HV322 loads, rating mode renders, legend totals, sort heading and order, cases rows with evidence links, year labels, stamp versions identical (43 refs).
**Result:** pass (assistant's find_cases needs a service restart by the owner)
**Issues:** event-rich products still have busy chart labels; case rows wrap at narrow widths when the discontinuation flag shows.

**Update [2026-09-24]:** owner restarted the service; live `find_cases` verified through the public URL ("Find me cases of cannibalisation" → find_cases → OP101 −94.6%, IR101 ×2).

## [2026-09-24] Portfolio table fix + proxy validation (diagnosis)
**Built:** numeric headers flush right over their numbers (the header used row-reverse with flex-end, which aligned left); new "Review volume" column (new + refurbished), default sort.
**Tested:** live: every numeric label's right edge equals its column's value edge (522/522, 715/715, 931/931, 1173/1173, 1395/1395).
**Proxy check (owner asked whether reviews can stand in for demand):** Amazon Best Sellers Rank (sales-based, one snapshot per listing at crawl, Home & Kitchen category) vs review counts, SharkNinja brand-store listings with a BSR (n=431), Spearman with bootstrap 90% ranges: last-12-month reviews -0.71 [-0.75, -0.65]; last 6 months -0.68; all-time written reviews -0.46; all-time star ratings -0.65; active listings (n=242) -0.81; within product type -0.65 to -0.85. Supports reviews as a cross-sectional demand proxy; does not validate changes over time (only one BSR snapshot; crawl date not recorded).
**Result:** pass
**Issues:** the time-series use of reviews (event tests) remains unvalidated against sales.

## [2026-09-23] Review — Reframing assessment (no code changed)
**Built:** docs/REVIEW_BRIEF.md (project brief and full field inventory); independent Fable review saved as docs/REVIEW_FABLE.md. It recommends reframing from "demand evidence" to post-purchase quality insight (complaint themes, time to failure, rating decline over product life, refurbished gap), with the event tests moved to a Method appendix.
**Tested:** Re-derived the reviewer's headline numbers with independent queries: rating decline year 1 vs years 3-4, 60 products (reviewer 61), -0.47 stars, 58 of 60 fall, low-star share 11.1% to 23.6%; refurbished gap -0.12 naive vs -0.05 within the same product and year (62 cells); stated time to failure median 6 months, 86% within 12, 23% at exactly 12 (looser regex, n=6,816 vs 3,162, same shape); S3501 low-star share 20.7% (2021), 41.0% (2022), 53.3% (2023); discontinued flag never "Yes" (905 No, 4 false).
**Result:** pass (numbers reproduce)
**Issues:** the general rise in low-star share has no non-SharkNinja comparator on disk, so it may be Amazon-wide; the full raw files were streamed, not kept, so a comparator needs a fresh streamed extract.

## [2026-09-23] Reframe R1 to R3 — Peer brands, complaint themes, post-purchase analysis
**Built:** `scripts/extract_comparators.py` (streams the public Home & Kitchen and Appliances files, keeps Bissell, Dyson,
iRobot, Keurig, Instant Pot; 67.4M review lines read, 666,776 kept); `pipeline/comparators.py` (same rules, units only,
types SharkNinja also sells: 1,404 units, 443,634 reviews); `pipeline/themes.py` (24 keyword themes plus stated
time-to-failure bands, all reviews both sets); `pipeline/lifecycle.py` (pq_* tables: life-cycle drift, curve, trend,
theme shares by type and product, failure bands, refurbished cells and arrival themes, case studies, theme meta, peer
brands); `pipeline/export_web.py` rewritten for the new front end. Fix in `rules.py`: coffee checked before blender
(6 "Coffee Bar Auto-iQ" listings were typed blender; dry run showed exactly those 6 change). Full pipeline rerun; event
tests now 2,822 events, 808 testable, 0 survive FDR, held-out placebo false-alarm 8.9%.
**Tested:** theme precision on blind labels (Sonnet labeller, 25 low-star reviews per theme; round 2 re-sampled the 6
themes whose rules were tightened): all 24 themes 0.80 to 1.00, overall 0.89 on 600 pairs (`eval/theme_precision.csv`);
spot-read 10 round-2 labels. Case-study baseline changed from SharkNinja's own type trend (which contains the product;
S3501 is most steam mops) to the peer brands' type trend. Headline numbers in `data/clean/postpurchase_report.md`.
**Result:** pass
**Issues:** the peer comparison changes the earlier review's story: the rise in low-star share is shared by peers
(peers 13.5% to 28.0%, SharkNinja 14.2% to 23.7%, 2015 to 2022) and ratings fall with product age for peers too
(-0.37 vs -0.46). Peer sets are thin for some types (irons n=1 product in drift, robots n=3 SharkNinja).

## [2026-09-23] Reframe R5 — Assistant tools
**Built:** `app/tools.py`: get_product_complaints, compare_product_type (SharkNinja-only answer when peers lack the
type), rank_products (low_star_share, complaint_share by theme, rating_change), find_cases (complaint jumps),
get_findings (new), search_reviews theme filter and helpful sort, set_view defaults to rating. Event and growth tools
removed. New system prompt; mock intents; tests; 21 real-model cases.
**Tested:** pytest 70 passed (mock mode); smoke calls of every tool against the real tables.
**Result:** pass (real-model run pending)
**Issues:** none

## [2026-09-23] Reframe R4 — Front end "After the Sale"
**Built:** Sonnet builder rebuilt `web/` to `docs/SPEC_after_the_sale.md` (Overview with key findings and a product-type
table; Product page with complaint mix vs type and peers, quotes, year table, life-cycle chart, refurbished block;
Findings with six sections; Method with peer brands, theme precision table and the event-test appendix; event page
removed with redirect). My review pass fixed: drift shown as percent (stars), trend and headline years (2015 to 2022
instead of noisy 2012 and partial 2023), failure copy that read as failure rates, "X, not Y" phrasing, a wrong
"1 in 6" subtitle, raw type names, clipped chart labels (wrapping), sparse-month rating noise (months under 5 reviews
hidden), year highlighting on small samples, arrival breakdown on under 30 low-star refurbished reviews, Method claims
that peers were entity-resolved (they are listing-level) and unlabelled totals. Export: NaN written into 361 product
files fixed at source (`allow_nan=False` now fails loudly). Peer set cleaned after reading the top peer listings per
type: carpet shampooers, CrossWave, SteamShot, Spinwave, robot mops, air-fryer lids and boards excluded; peer irons
(steam cleaners, steamer baskets, fans coloured "Iron") and manual sweepers dropped; peer brand counts only with 200+
reviews in a type.
**Tested:** Browser pane at 1440 px and 375 px (no horizontal scroll), Overview, Product (S3501), Findings, Method,
no console errors; pytest 71 passed; real Haiku run 20 of 21 (the ambiguous "show me the vacuum" case skips the
lookup about 1 run in 5 after a prompt example; accepted as a known limit); nginx switch script dry-run on a copy of
the live config (idempotent).
**Result:** pass (not deployed)
**Issues:** chat clarification rule is probabilistic on Haiku.

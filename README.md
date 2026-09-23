# Demand Evidence

Pick a Shark or Ninja product and see what moved its Amazon demand, and what did not.

**Live app:** https://apps.mohithgujjula.com/demand-evidence/
**Write-up:** https://mohithgujjula.com/work/#demand-evidence

This is an independent analysis project. It is not affiliated with, endorsed by or built for SharkNinja or Amazon.
Product names and trademarks belong to their owners.

## What it answers

Three questions, tested on every product where the data allows:

1. When a sibling model launches in the same family, do the older product's reviews change?
2. When refurbished (Amazon Renewed) units of a product appear, do new-unit reviews change?
3. After a month of unusually low ratings, does review volume change?

Review volume stands in for demand. There is no price, stock, sales-rank or seller history in the data, so those
questions are out of scope, and the tool says so.

## What it found

- **Single events cannot be detected in review data.** Each event is compared with a matched group of similar products
  that had no such event. A fake-date (placebo) test showed the natural swings are large: without a correction, about
  1 in 10 fake events would be called "moved". After a false-discovery check across all 819 testable events, none holds up.
- **Averages across events do hold** (product-level bootstrap, 90% ranges, compared with the placebo baseline):
  - after a sibling launch, older products' reviews ran about 42% higher (+24% to +64%, 113 products);
  - once refurbished units appeared, new-unit reviews ran about 40% higher (+15% to +72%, 54 products);
  - after a low-rating month, the next 3 months ran about 9% lower (−17% to −1%, 92 products).
  The data shows these happening together and cannot say what caused them: launches may be timed when a line is
  growing, and refurbished units appear once a product has sold a lot.

## How it works

| Step | Code | What it does |
|---|---|---|
| Data | `DATA_SOURCES.md` | Survey of free sources; Amazon Reviews 2023 (McAuley Lab, UCSD) chosen |
| Clean | `pipeline/rules.py`, `pipeline/clean.py` | Deterministic rules: model numbers, accessories vs units, product type, other brands that share the store name |
| Match | `pipeline/match.py`, `pipeline/resolve_sn.py` | 1,967 listings joined into 1,138 products (colours, retailer codes, refurbished listings, bundles) |
| Measure | `eval/` | Walmart-Amazon benchmark F1 0.852 (held-out test); SharkNinja blind-labelled held-out pairs: precision 0.869, recall 0.914 |
| Timeline | `pipeline/panel.py` | Monthly reviews and rating per product, new and refurbished series, explicit zero months; data complete through March 2023 |
| Test | `pipeline/events.py` | Event tests with matched comparison groups, placebo calibration, false-discovery control, pooled averages |
| Export | `pipeline/export_web.py` | Static JSON for the front end |
| Front end | `web/` | Plain HTML, CSS and JavaScript; no framework, no build step |
| Assistant | `app/` | Flask service; Claude Haiku 4.5 with seven read-only tools, rate limits and a daily spend cap |

`PLAN.md` and `BUILD_LOG.md` record every decision, check and correction along the way. `docs/` holds the build specs
and `design/storyboard/` the approved storyboard frames.

## Run it

The data is not included (see below). To rebuild it:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

1. Download the Home_and_Kitchen and Appliances metadata and the Home_and_Kitchen reviews from
   https://amazon-reviews-2023.github.io/ and filter them to Shark, Ninja and Euro-Pro listings into
   `data/raw/amazon2023/meta_sharkninja.jsonl` and `reviews_sharkninja.jsonl` (the filter is described in `BUILD_LOG.md`, Phase 0).
2. Matching benchmarks (optional, for `eval/bench_eval.py`): `matchbench/Walmart-Amazon`, `Abt-Buy`, `Amazon-Google` from
   Hugging Face into `data/raw/benchmarks/`.
3. Run the pipeline in order: `clean.py`, `resolve_sn.py`, `panel.py`, `events.py`, `export_web.py`.
4. Serve the page: `cd web && python3 -m http.server 8765`, or run the assistant with the page:

```bash
.venv/bin/pip install -r app/requirements.txt
cd app && LLM_MODE=mock SERVE_STATIC=1 ../.venv/bin/python server.py   # http://127.0.0.1:5055
```

`LLM_MODE=mock` runs a rule-based stand-in at no cost. For the real model set `LLM_MODE=anthropic` and
`ANTHROPIC_API_KEY` in `app/.env` (see `app/.env.example`). Tests: `.venv/bin/python -m pytest app/tests`.

## Data and licence

The code is released under the MIT licence (`LICENSE`). The data is not: Amazon Reviews 2023 is published by the
McAuley Lab at UC San Diego (Hou et al., 2024) and the matching benchmarks by the UW–Madison Magellan project; use them
under their providers' terms. No review text or listing data is redistributed in this repository.

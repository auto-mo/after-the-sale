# After the Sale

What Shark and Ninja owners report after they buy, compared with Bissell, Dyson, iRobot, Keurig and Instant Pot.

**Live app:** https://apps.mohithgujjula.com/after-the-sale/
**Write-up:** https://mohithgujjula.com/work/#after-the-sale

This is an independent analysis project. It is not affiliated with, endorsed by or built for SharkNinja, Amazon or
any of the peer brands. Product names and trademarks belong to their owners.

## What it answers

Pick a product and see what its owners complain about, when they say it stopped working, how its rating changes over
its life, and how refurbished units compare with new, each set against SharkNinja's average for that product type and
against peer brands selling the same type.

The data is written Amazon reviews, which are self-selected. Complaint shares are shares of 1 and 2-star reviews that
mention a complaint, never failure or return rates. Nothing here measures sales or demand, and nothing claims a cause.

## What it found

All figures are from new-unit reviews through March 2023.

- **Ratings fall as products age, for every brand.** Comparing year 1 with years 3 to 4 of the same product,
  58 of 60 SharkNinja products fell (average -0.46 stars) and 80 of 85 peer-brand products fell (-0.38).
- **The rise in 1 and 2-star reviews is shared.** From 2015 to 2022 the share went from 12% to 25% for SharkNinja and
  from 12% to 26% for the peer brands (equal weight per product type, using the six types both sets sold every year).
- **What differs is what owners complain about.** Share of 1 and 2-star reviews, SharkNinja vs peers: coffee maker
  leaks 16% vs 5%; robot vacuum app and connection problems 14% vs 6%; stick vacuums heavy or awkward 8% vs 2%;
  multicooker coating peeling 4% vs 0.5%.
- **Owners who say when a product stopped working** typically say about 6 months for SharkNinja and 4 for the peers
  (medians of 4,423 and 8,348 reviews that state a time; owners round to 6, 12 and 24 months).
- **Refurbished units rate about the same as new** for the same product in the same year (-0.04 stars across 59
  product-years), but their low-star reviews mention missing parts three times as often (2.9% vs 0.9%) and arriving
  damaged or used 2.4% vs 0.7%.
- **Case studies**: products whose share of 1 and 2-star reviews jumped in one year beyond the peers' change that
  year, such as the S3501 steam mop (21% in 2021 to 41% in 2022, with "no steam" rising).

An earlier version asked what moved each product's review volume (sibling launches, refurbished units appearing,
low-rating months). Of 2,806 events, 806 were testable and none survived a false-discovery check, so those tests are
kept in the code and described on the Method page, and the tool makes no demand claims.

## How it works

| Step | Code | What it does |
|---|---|---|
| Data | `DATA_SOURCES.md`, `scripts/extract_comparators.py` | Amazon Reviews 2023 (McAuley Lab, UCSD), streamed and filtered to SharkNinja and five peer brands |
| Clean | `pipeline/rules.py`, `pipeline/clean.py`, `pipeline/comparators.py` | Deterministic rules: model numbers, accessories vs units, product type, other brands sharing a store name; peer listings of kinds SharkNinja does not sell are left out |
| Match | `pipeline/match.py`, `pipeline/resolve_sn.py` | 1,967 SharkNinja listings joined into 1,137 products (colours, retailer codes, refurbished listings, bundles) |
| Measure | `eval/` | Matcher: Walmart-Amazon F1 0.852; SharkNinja blind-labelled pairs precision 0.948, recall 0.917 after adjudication. Complaint themes: blind-labelled precision 0.80 to 1.00 per theme, 0.89 overall |
| Timeline | `pipeline/panel.py` | Monthly reviews and rating per product, new and refurbished, complete through March 2023 |
| Themes | `pipeline/themes.py` | 24 keyword complaint themes and stated time-to-failure bands |
| Analysis | `pipeline/lifecycle.py` | Rating over product life, trend, theme shares by type, failure bands, refurbished comparison, case studies |
| Appendix | `pipeline/events.py` | The earlier event tests, with placebo calibration and false-discovery control |
| Export | `pipeline/export_web.py` | Static JSON for the front end |
| Front end | `web/` | Plain HTML, CSS and JavaScript; no framework, no build step |
| Assistant | `app/` | Flask service; Claude Haiku 4.5 with read-only tools, rate limits and a daily spend cap |

`PLAN.md` and `BUILD_LOG.md` record every decision, check and correction. `docs/REVIEW_FABLE.md` is the independent
review that led to the reframe.

## Run it

The data is not included (see below). To rebuild it:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

1. Download the Home_and_Kitchen and Appliances metadata and the Home_and_Kitchen reviews from
   https://amazon-reviews-2023.github.io/ and filter them to Shark, Ninja and Euro-Pro listings into
   `data/raw/amazon2023/meta_sharkninja.jsonl` and `reviews_sharkninja.jsonl` (the filter is described in
   `BUILD_LOG.md`, Phase 0). Run `scripts/extract_comparators.py` for the peer brands (it streams the files).
2. Matching benchmarks (optional, for `eval/bench_eval.py`): `matchbench/Walmart-Amazon`, `Abt-Buy`, `Amazon-Google`
   from Hugging Face into `data/raw/benchmarks/`.
3. Run the pipeline in order: `clean.py`, `resolve_sn.py`, `panel.py`, `events.py`, `comparators.py`, `themes.py`,
   `lifecycle.py`, `export_web.py`.
4. Serve the page with the assistant in its free rule-based mode:

```bash
.venv/bin/pip install -r app/requirements.txt
cd app && LLM_MODE=mock SERVE_STATIC=1 ../.venv/bin/python server.py   # http://127.0.0.1:5055
```

For the real model set `LLM_MODE=anthropic` and `ANTHROPIC_API_KEY` in `app/.env` (see `app/.env.example`).
Tests: `.venv/bin/python -m pytest app/tests`.

## Data and licence

The code is released under the MIT licence (`LICENSE`). The data is not: Amazon Reviews 2023 is published by the
McAuley Lab at UC San Diego (Hou et al., 2024) and the matching benchmarks by the UW–Madison Magellan project; use them
under their providers' terms. No review text or listing data is redistributed in this repository.

# PLAN: from raw data to a usable, joined dataset, then simulations

Living document. Updated as each step finishes. Latest status is at the top of each phase.

## Final goal
A clean, joined SharkNinja dataset (treating 2023 as "now") where every listing maps to one
canonical `product_id`, with a monthly time panel per product. It should support simulations
over a chosen period to find what moved what (for example, did a new model's launch slow its
predecessor's reviews?). Matching accuracy is proven first on a public benchmark that has
ground truth.

## Hard facts that shape the plan (measured 2026-09-23)
- **No product overlap between datasets.** Zero Shark, Ninja or Euro-Pro rows in Walmart-Amazon,
  Abt-Buy, Amazon-Google or PriceRunner. A cross-dataset JOIN on products is not possible.
  Cross-dataset alignment is a **shared column layout**, not a join.
- **Real joins exist inside sources:**
  - Amazon 2023 reviews → listings on `parent_asin`: 293,270 of 293,270 match (100%).
  - Reviews also carry a variant-level `asin` (520 distinct child ASINs differ from their parent).
  - Benchmarks: left table ↔ right table through the labelled pairs files.
- **Weak fields:** price is filled for 35% of SharkNinja brand-store listings, and there is no
  price history at all. Rating, review count and review dates are complete.
- **Benchmark prices are text** with `'nan'` for missing.

## Shared column layout (crosswalk)

| Canonical field | Amazon 2023 listings | Walmart-Amazon (both sides) | Abt-Buy | Amazon-Google | PriceRunner |
|---|---|---|---|---|---|
| `source`, `retailer` | amazon (store: Shark / Ninja / Amazon Renewed) | walmart / amazon | abt / buy | amazon / google | vendor id |
| `record_id` | `parent_asin` | `id` | `id` | `id` | `Product ID` |
| `title` | `title` | `title` | `name` | `title` | `Product Title` |
| `brand` | `details.Brand`, else `store`, else title | `brand` | inside `name` | `manufacturer` | inside title |
| `model_no` | `details.Item model number` / `Model Name` / "Model Number:" in `features` / title | `modelno` (94% Walmart, 71% Amazon) | inside `name` | inside title | inside title |
| `category` | `categories[]` path | `category` | none | none | `Category Label` |
| `price` | `price` (float) | `price` (text) | `price` (text) | `price` (text) | none |
| `rating`, `rating_count` | `average_rating`, `rating_number` | none | none | none | none |
| same-product truth | none (we build it) | labelled pairs | labelled pairs | labelled pairs | `Cluster ID` |
| time | review `timestamp`, `details.Date First Available` | none | none | none | none |

## Phases

### Phase 0: Data discovery and snapshot. DONE
See `DATA_SOURCES.md`, `explore/data_snapshot.html`, `BUILD_LOG.md`.

### Phase 1: Crosswalk and join-key audit. DONE (this document)

### Phase 2: Pattern discovery. DONE
Full write-ups: `explore/patterns/amazon_sharkninja.md`, `explore/patterns/benchmarks.md`
(rules code alongside). Numbers marked ✓ were re-queried independently by the orchestrator.

**Benchmarks (Walmart-Amazon, 10,242 pairs)**
- ✓ When both sides have a model number, normalised exact match holds for 76% of true matches
  and **0% of non-matches**. It is precise but capped, because 32% of matched pairs miss a model
  number on one side.
- ✓ Brand is equal in 73% of non-matches, so it is a blocking filter, not a match rule.
- Title word overlap (Jaccard) alone gives F1 of about 0.42 to 0.50 on the held-out test splits.
  It is useful only as a blended signal.
- Price: matched pairs have a median gap of 11 to 17%, against 39 to 49% for non-matches. It is a
  supporting signal only.
- All missing values are the string `'nan'`; prices already parse 100%.

**SharkNinja Amazon 2023**
- ✓ `details['Item model number']` is filled for 1,353 of 2,012 listings (67%). A bracketed-title
  fallback takes it to 70.5%. A bare-title regex might reach about 94% (agent estimate, needs a
  stoplist and verification).
- Only `AMZ` is a confirmed retailer suffix (11 listings). Stripping suffixes collapses 1,032 model
  numbers to 1,000 bases. Single-letter `C`/`Q` stripping is risky and must be validated per group.
- ✓ Refurbished (Renewed) listings: 447 of 843 have a model number, and **only 145 link to a
  brand-store listing by exact model number (163 via base model).** So most refurbished listings
  need title-based matching, not a key join.
- ✓ The third-party brands (LYTIO 87, Lutema 47) are all on Renewed listings. They are
  refurbishers, not off-brand products in the Shark or Ninja stores.
- Product type from title keywords: 81% classified; a category fallback for the rest is proposed.
- Capacity is parseable for 31% of listings and wattage for 29%.
- ✓ 76 of 1,012 listings with a launch date have reviews dated **before** launch, which is
  evidence that Amazon carries reviews over across listings. The time panel must handle this.
- 48% of reviews attach to a variant (child) ASIN; about 1% are duplicate rows; 88% are
  verified purchases.

### Phase 3: Cleaning. DONE (2026-09-23)
Code: `pipeline/rules.py` (pure rules) and `pipeline/clean.py` (DuckDB + pandas). Coverage for every rule is in
`data/clean/cleaning_report.md`. Outputs in `data/clean/`: `sn_listing`, `sn_review`, `rejected_reviews`,
`bench_listing`, `bench_pair`, `pricerunner_offer` (all parquet).

**SharkNinja listings (2,012, none dropped, all flagged)**
> Counts below are as of the first Phase 3 run. The Phase 4 rule changes (accessory detection, core model, ASIN
> rejection) moved them; current values: model_no 78.8%, accessory/part 269 (was 439), 761 core models.
> `data/clean/cleaning_report.md` is always current.
- `model_no`: 80.7% (was 67% from the details field alone). Sources: details 1,136, title 384, bracketed title 57,
  first of several title codes 46 (low confidence). Accessory titles keep their "for NV500, NV501" codes in a
  separate `compatible_models` field, so a spare part is never joined to the machine it fits.
- `base_model`: AMZ always stripped. Other suffixes (REF, CO, WM, Q, C, BK and similar) are stripped only where a
  sibling model exists: 64 listings, and all 34 merge groups were checked by eye.
- ✓ **Refurbished → brand-store join by base_model: 413 of 843 (49%)**, up from 145 on the raw field.
- `maker`: sharkninja 1,964; unrelated 18 (Sharkk, Shark Skinz, NINJA Brand rug pads, a TMNT bed set: the store
  name collides with other brands); third_party_compatible 10; unverified 20 (Fantom vacuums, generic items).
- `product_type`: category-path first (it is cleaner than title keywords), with title fallback. 23 remain unclassified,
  mostly the unrelated items. Categories are sometimes wrong (a blender filed under "Banners").
- Units: capacity in quarts 35%, wattage 36%. Price 29% (brand store 35%). Launch date 50%.
- Spot checks: 20 of 20 title-sourced models correct; 15 of 15 sampled refurbished → brand-store links correct.

**Reviews:** 290,614 kept, with 2,656 exact duplicates moved to `rejected_reviews` with a reason. 0 orphans.
13,811 reviews on 76 listings are dated before the listing launched; they are kept and flagged `before_launch`.

**Benchmarks:** unified into `bench_listing` (shared layout) and `bench_pair` (train/valid/test).

### Phase 4: Entity resolution. DONE (2026-09-23)
Code: `pipeline/match.py`, `pipeline/resolve_sn.py`, `eval/bench_eval.py`, `eval/sample_pairs.py`, `eval/sn_eval.py`.
Outputs: `data/clean/sn_listing_product.parquet` (listing → `product_id`, method, score, reason), `sn_product.parquet`,
`sn_unmatched.parquet` (330 listings with no confident match, with their best candidate, for review).

**Matcher (deterministic, layered):** model agreement (equal, prefix or containment) → match; genuine model conflict →
non-match unless one side's code is in the other title; otherwise title overlap + model-in-title + price, minus a
penalty when the numbers in the titles differ. Tuned only on Walmart-Amazon train+valid.

| Benchmark (held-out test) | Precision | Recall | F1 | Model number only | Title only |
|---|---|---|---|---|---|
| Walmart-Amazon | 0.870 | 0.834 | **0.852** | 0.787 | 0.429 |
| Abt-Buy | 0.930 | 0.777 | **0.847** | 0.636 | 0.503 |
| Amazon-Google (software titles) | 0.469 | 0.543 | **0.503** | 0.055 | 0.463 |

**SharkNinja resolution:** main units key on `core_model` (letters+digits: WS642BL = WS642GN); accessories use a
separate `SN-P-` namespace and link only on an identical title; accessory detection is position-based (a part word
before any unit noun). Result: 1,994 in-scope listings → **1,122 products**; 351 products have several listings;
221 have both a brand-store and a refurbished listing; 57% of refurbished listings share a product_id with a brand-store listing.

| SharkNinja blind-labelled sets | Pairs | Precision | Recall (sampled pairs) |
|---|---|---|---|
| Dev set (used for tuning, so optimistic) | 138 | 0.953 | 0.854 |
| **Held-out test set (never tuned on)** | 118 | **0.869** | **0.914** |

Held-out by decision type: model-key links 32/36 correct, title matches 13/15, clusters 8/10, hard look-alikes correctly
kept apart 38/40, near misses correctly kept apart 14/17. The sample is stratified, so these are not population rates.

**Manual check of the suffix question (2026-09-23), from the listings' own fields:**
- WS642 / WS642BL / WS642GN: identical dimensions, weight, wattage, voltage, features; only colour and price differ → same.
- S4701 / S4701D: same title and specs, and an identical Amazon rating pool (4.2 from 183) → same.
- S3601 / S3601D: identical dimensions and weight → same. AF100 / AF101: identical spec title → same (manual alias).
- NV480 / NV482: shared 507-rating pool → same (manual alias, medium). S3501N, EP033TN: too little data to confirm.
- HV301 / HV302: one listing contradicts itself (title HV302, field HV301) → left unresolved.
- Identical rating pools are only a signal together with similar titles: at 200+ ratings, 16 of 37 shared pools were
  unrelated products (coincidence), so it is not used as a matching rule.

**Changes from the check:** a model named in the title beats a conflicting details field (6 listings); manual alias table
`data/manual/model_aliases.csv`; self-empty versions (WS642AE, RV1000AE…) are their own product `SN-<core>-SE` (26
listings); bundles joined with "+" are their own product `SN-B-…` (27); more accessory words; fixed regression list
`eval/accessory_title_cases.py` (31 titles, 0 errors).

**Current:** 1,967 listings in scope → **1,138 products** (870-odd units + ~250 accessories + bundles).
Held-out test: raw labels precision 0.869 / recall 0.914 (118 pairs); with evidence-based adjudication of 5 disputed
pairs (`eval/sn_test_adjudications.csv`, decided from listing data, not matcher output) precision 0.948 / recall 0.917 (115 pairs).

### Phase 5: Time panel. DONE (2026-09-23)
Code: `pipeline/panel.py` (DuckDB SQL). Outputs: `data/clean/sn_panel_month.parquet` (product × channel × month),
`sn_product_event.parquet`, `sn_product_summary.parquet`, `panel_report.md`.
- Owner decisions applied: reviews dated before a listing launched are kept at product level (13,811); refurbished
  reviews are a separate `renewed` channel (21,005) next to `new` (268,371).
- ✓ Reconciliation: 289,376 reviews in scope = sum of the panel. 0 missing months; 70,317 zero months explicit.
  1,238 reviews excluded (unrelated brands). 1,133 products have at least one review.
- **Coverage cut-off:** monthly volume is steady at ~3,000–4,100 through 2022, then drops (Apr 2023 2,007 → Aug 418 →
  Sep 23). This is a crawl artefact, so `data_complete` is false after **2023-03**. Treat March 2023 as "now".
- Launch date = earliest evidence (listed "first available" date or first review). Sources: listed date 492, first review
  proxy 417, first refurbished review proxy 150, first review earlier than listed date 79.
- `family` = letter prefix of the model (NV, AF, BL, QB…): 772 products across 148 families, for predecessor/successor analysis.
- Scale note: the dataset holds written reviews only (AF101: ~5,900 reviews vs 45,929 star ratings), so volume is a demand proxy.

**Usable-data exit check:** every in-scope listing has a product_id (singletons get their own); 77% of brand-store listings
(887 of 1,151) are linked by model or match rather than left alone; matcher precision/recall measured (Phase 4); panel has
explicit zeros. The 90% linked target is not met because many listings have no model number and a generic title; they are
kept as separate products, not forced.

### Side quest: official catalogue (2026-09-23)
Sandboxed research agent → `explore/catalog_sources.md`. No complete public SharkNinja catalogue found. Best sources:
ManualsLib Shark pages (✓ re-fetched: "more than 1417 Shark Vacuum Cleaner manuals", roughly 300–400 distinct models;
vacuums only), support.sharkninja.com model-series pages (official, but JS-rendered, not fetched), SEC F-1 (category
counts only, 31 vs 35 subcategories unresolved). **Sanity check:** our data has 378 vacuum products (312 with a model
key), inside ManualsLib's rough 300–400 range. Snippet-level (unverified) support for the aliases: AF101 = AF100 plus rack
and warranty; NV480/481/482/484 are one official series; WS642AE = self-empty WS642; S3601D = S3601 plus extra head and pad.
No prompt-injection content encountered.

### Phase 6 scope (owner, 2026-09-23)
Confirmed questions: (1) cannibalisation after a family launch, (2) refurbished-units effect, (3) rating shocks → later volume.
Owner also wants granular questions (stock-outs, price changes, sales rank, buy box, first-party vs third-party).
**Data gap:** the Amazon 2023 set has no price history, no stock status, one sales-rank snapshot per listing, and no
seller/buy-box data. Answering these needs a history source; the candidate is Keepa (Amazon price, sales rank, buy box,
offer and seller history per ASIN; paid, around €49/mo reported, not verified). Decision pending with owner. Until then,
granular items can only be what-if scenarios with stated assumptions, clearly labelled as such, never presented as findings.

### Build decisions (owner, 2026-09-23)
- Build everything: analyses (Phase 6), front end (Phase 7), chatbot (Phase 8). Storyboard v2 is the approved design,
  plus: the guided tour covers the chatbot; the chat panel offers clickable suggested prompts.
- Chatbot model: Claude Haiku 4.5. Security and overuse plan approved: key server-side on Jarvis, read-only tools,
  per-visitor rate limit, Cloudflare Turnstile, daily dollar cap in the service, reply and turn caps, invite code optional.
- Testing: mock LLM mode for all plumbing at zero cost; a short list of cases that need the real model is run on Haiku
  once the owner supplies the key. No real API calls before that.
- Risks: API cost (mock mode until the key; daily cap after), key exposure (server-side only), shared host (deploy is a
  separate, confirmed step with the capacity check from CLAUDE.md §12d), prompt injection via review text (tools read-only).

### Phase 6: Simulations. DONE (2026-09-23)
Code: `pipeline/events.py`. Outputs: `sn_event_test` (one row per product event), `sn_event_band` (comparison band per
relative month), `sn_event_control`, `sn_event_pooled`, `events_report.md`.
- Events: sibling launch (same family and type; same-month launches merged), refurbished units appear, low-rating month
  (>= 0.3 below trailing 12-month average, >= 10 reviews). 2,817 events.
- Comparison group: up to 10 products, same type, other family, matched on life stage and prior volume; looser tiers
  (relaxed, then broad category) only when stricter ones find < 3, and flagged.
- **Placebo calibration (fake dates):** the first design said "Moved" on 21% of fake events. Causes: ranges ignored natural
  swings; end-of-life products looked like effects. Fixed by life-stage matching and a range widened by the natural swing
  calibrated on placebo set A; the held-out placebo set B false-alarm rate is 10.4%.
- **Per-event verdicts:** 819 events testable; 79 "Moved" against ~85 expected by chance, and **0 survive false-discovery
  control (BH, q = 0.10)**. Final: No clear change 819, Not enough data 1,998. "Did not move" is not offered: natural swings
  make a ±15% range impossible with review data.
- **Pooled averages (cluster bootstrap by product, vs placebo):** sibling launch +42.5% [+24, +64] (561 events, 113 products);
  refurbished units appear +40.0% [+15, +72] (54 products); low-rating month −9.2% [−17, −1] (92 products).
  Associations, not causes: sibling launches may cluster when a line is growing (a halo, or marketing), and refurbished units
  appear when a product has sold a lot (more returns). These are the portfolio findings the tool can stand behind.

### Phase 7: Front end + Phase 8: chatbot. BUILT LOCALLY (2026-09-23)
See BUILD_LOG. Remaining: (1) run `app/run_real_cases.py` on Haiku once the owner supplies the key (cap $0.50), fix what it shows;
(2) deploy to Jarvis under apps.mohithgujjula.com/demand/ (nginx static + /demand/api/ proxy, systemd service, .env with key,
capacity check first per CLAUDE.md §12d; needs owner's sudo); (3) optional Cloudflare Turnstile site key (owner creates it). ("what moved what")
Pick a window (for example 2019 to 2023). Run event studies against a baseline:
- New-model launch → predecessor review velocity and rating (cannibalisation).
- Renewed listing appears → new-listing review velocity and rating.
- Rating shocks → later review volume.

**Limits to state:** review volume stands in for demand; there is no price history or sales data.

### Phase 7: Simulation front end (DEFERRED until the data work is done; owner request 2026-09-23)
Not over-built, but useful: well-chosen visuals where they earn their place, and deliberate controls
(product/product-type picker, time window, event selection, baseline choice). Run the UI gate (ui-craft,
hallmark) when this starts. Brief the surface and lock design decisions before building.

### Optional extension
Stream Amazon 2023 Electronics and Office metadata to find the Walmart-Amazon benchmark's Amazon
products (by model number). That would give the benchmark a real review timeline, making it a
second, cross-retailer time series. Cost: a multi-GB stream on the Mac only.

## "Usable data" exit criteria
- At least 90% of SharkNinja brand-store listings carry a `product_id`, with a measured
  matcher precision and recall.
- Monthly panel with explicit zero months (no silent gaps).
- Every cleaning rule documented with its coverage.

## Risks
- No data loss risk: raw files are read-only and outputs are separate.
- No cost: everything runs locally on the Mac, not Jarvis.
- **Main analytical risk:** review counts are a proxy. Any "what moved what" finding is
  correlational and must be framed that way.

## Open questions for the owner
1. Today is a weekday, and the standing rule is plan, docs and diagnosis only. Phases 1 and 2 are
   diagnosis. Is Phase 3 onward (building clean tables) OK to run now, or wait for the weekend?
2. "What moved what": is review velocity and rating the right outcome to explain, given there is
   no sales or price history?

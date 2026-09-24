# Review brief: what can this data honestly tell us?

Written 2026-09-23 for an independent review. Paths below are relative to the repository root.

## Where the project came from
- Self-initiated portfolio project by Mohith Gujjula while interviewing at SharkNinja. Nobody asked for it.
- Original question: is a Ninja product's weak Amazon performance Amazon-specific or market-wide? Constraint: free,
  automated data only, no hand gathering, no paid APIs, deterministic methods before LLMs.
- The only usable free data turned out to be **Amazon Reviews 2023** (McAuley Lab, UCSD), treated as a snapshot with
  "now" = March 2023. No other retailer, no price history, no sales, no stock, no Buy Box, no sales-rank history.

## What got built (live: https://apps.mohithgujjula.com/demand-evidence/)
- Deterministic cleaning and entity resolution: 1,967 listings into 1,138 products (colour variants, retailer codes,
  refurbished listings, bundles, accessories, other brands that share a store name). Matcher F1 0.852 on the
  Walmart-Amazon benchmark; SharkNinja held-out precision 0.948 / recall 0.917 after adjudication.
- Monthly panel per product: review count and average rating, new vs Amazon Renewed (refurbished) channel.
- Three event tests with matched comparison groups, placebo calibration and false-discovery control:
  sibling launch (cannibalisation), refurbished units appearing, low-rating month.
- Front end (portfolio, product timeline, event evidence, findings, method) and a Claude Haiku chat assistant with
  read-only tools.

## What was found
- **No single event is detectable.** 0 of 819 testable events survive the false-discovery check; the placebo false-alarm
  rate before correction was about 10%.
- Pooled averages hold but are associations: after a sibling launch older products' reviews +42.5% [+24, +64];
  after refurbished appears, new-unit reviews +40.0% [+15, +72]; after a low-rating month, next 3 months −9.2% [−17, −1].
  These are most likely selection (launches and refurbished follow growth), not effects.
- Review counts do track the Best Sellers Rank snapshot across products (Spearman −0.71 for last-12-month reviews,
  n=431, Home & Kitchen), so "more reviewed = more sold" is reasonable **across products at one point in time**. It is
  not validated **over time**, which is what every event test assumes.

## Why the owner is unconvinced
The product is framed as "demand evidence" and "what moved this product". The honest result is "nothing measurable
moved any single product" and the framing leans on a proxy only validated cross-sectionally. The owner is happy to drop
the original question and redo parts of the project; the aim is **insights this data genuinely supports**.

## Every field available (counted 2026-09-23)
**Listings (2,012 raw; `data/raw/amazon2023/meta_sharkninja.jsonl`, cleaned in `data/clean/sn_listing.parquet`)**
- Always present: title, average_rating, rating_number (count of star ratings, incl. those without text), images, store,
  parent_asin. Mostly present: categories 1,911, main_category 1,901, description 1,706, features (bullets) 1,681.
  Sparse: videos 845, **price 584** (single snapshot, 29%).
- `details` dict (counts of listings carrying each key): Item Weight 1,791; Brand 1,702; Manufacturer 1,471; Product
  Dimensions 1,400; Item model number 1,353; **Best Sellers Rank 1,197** (snapshot; top keys Home & Kitchen 447,
  Kitchen & Dining 416, Amazon Renewed 312, plus sub-category ranks e.g. Upright Vacuums 190, Countertop Blenders 143);
  Color 1,187; Special Feature 1,077; Included Components 1,038; **Date First Available 1,013**; **Is Discontinued By
  Manufacturer 909**; Power Source 728; Filter Type 640; Capacity 618; Form Factor 612; Wattage 590; Model Name 451;
  Voltage 446; Material 414; Warranty Description 380; Is Cordless 361; Is Dishwasher Safe 330; Number of Speeds 175;
  Noise Level 170; Country of Origin 143; and a long tail.

**Reviews (290,614 after cleaning; `data/clean/sn_review.parquet`)**
- rating (1★ 35,237 / 2★ 15,174 / 3★ 17,413 / 4★ 31,713 / 5★ 191,077), review title, review text (mean ~292 chars),
  timestamp (2002 to 2023, complete through 2023-03), verified_purchase (257,071 verified), helpful_vote (90,693 with
  at least one vote), user_id (279,390 distinct; 9,296 users reviewed 2+ SharkNinja products), child asin
  (139,548 reviews carry a variant asin different from the parent, i.e. which colour/size/bundle was reviewed).

**Derived by the pipeline**: product, family, product type, model/core model, capacity, wattage, accessory flag,
new vs refurbished channel, launch month, sibling relationships, event list and test results.

## Files worth reading
`PLAN.md`, `BUILD_LOG.md`, `README.md`, `DATA_SOURCES.md`, `docs/SPEC_*.md`, `pipeline/*.py`,
`data/clean/*_report.md`, `web/` (the front end), `app/tools.py` and `app/llm.py` (the assistant).
Python with pandas/duckdb: `.venv/bin/python`.

## Constraints to respect
Free data only, nothing paid, no scraping of live sites. No secrets printed. Do not modify project files or anything on
the server; this is a read-and-analyse review. Deterministic methods first; LLM only where it clearly earns its place
(e.g. reading review text at scale, and even then consider keyword/rule approaches first).

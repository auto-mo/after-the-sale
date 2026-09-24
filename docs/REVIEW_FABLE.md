# Independent review: what the SharkNinja Amazon review data can honestly say

Reviewer: independent senior-analyst pass, 2026-09-23. Read-only. Everything numeric below comes from a query I ran
in this session (scripts `01_` to `11_*.py` in this folder, run with the project `.venv`). Where I did not verify
something I say so. No project file or server was touched.

## 0. The short version

The engineering is good and should stay. The framing is the problem. "Demand evidence" and "what moved this
product" promise a causal, time-series claim that written Amazon reviews cannot carry, and the project's own results
say so (0 of 819 events survive false-discovery control; the pooled effects are selection). The data is, however,
unusually good at a different job: it is 290,614 dated, star-rated, verified-flagged owner statements about 1,138
resolved products across 20 product types, with a clean new-versus-refurbished split. That is a **product quality
and consumer-insights** dataset, not a demand dataset.

Tested against the data, the strongest honest findings are:

1. **Satisfaction falls as a product ages, for almost every product.** Among 61 products with at least 100 new-unit
   reviews in both their first year and years 3 to 4, the average rating drops 0.47 stars (median 0.42) and 59 of 61
   fall; the share of 1 to 2 star reviews doubles from 11.1% to 23.7% and rises in 61 of 61. Adjusting for the
   calendar-year trend leaves a 0.37-star drop, negative in 88% of products.
2. **Complaint themes are category-specific and quantifiable with rules, no LLM needed.** Robot vacuums: app and
   connectivity 23% of low-star reviews. Handheld vacuums: battery and runtime 13%, suction loss 7%. Coffee makers and
   irons: leaks 17% and 20%. Uprights: "stopped working" 17%, heavy or awkward 10%, brush roll 9%. Multicookers:
   coating peel 6%. A tightened keyword tagger reads cleanly by eye on 7 of 8 sampled themes.
3. **Owners who say when the product failed say "within a year" 87% of the time.** 3,162 low-star "stopped working"
   reviews name a time since purchase; the median is 6 months, 36% say 3 months or less. Medians by type run from
   3 months (food processors) to 10 months (coffee makers, steam mops).
4. **The refurbished satisfaction penalty is mostly an illusion of timing.** Naive gap is 0.12 stars (4.13 new vs
   4.01 refurbished). Compared within the same product and the same calendar year (59 cells, 37 products) the gap is
   0.04 stars and refurbished is lower in only 54% of cells. What is real about refurbished is fulfilment: missing
   parts (6.2% vs 1.9% of low-star reviews), dead on arrival (6.8% vs 3.5%), "this is not new" (2.5% vs 0.6%).

Recommendation: reframe the product as an **owner-feedback quality monitor** (working name candidates in section 4),
keep the pipeline, the panel, the UI shell and the assistant, rebuild the analysis layer around complaint tagging,
life-cycle drift and the refurbished fulfilment gap, and demote the event tests to an honest appendix.

## 1. Critique of the current framing and methods

### What is sound and should be kept

- **Cleaning and entity resolution** (`pipeline/rules.py`, `clean.py`, `match.py`, `resolve_sn.py`). Deterministic,
  documented, benchmarked on public ground truth and on a blind held-out SharkNinja set. Matcher F1 0.852 on
  Walmart-Amazon, held-out SharkNinja precision 0.948 / recall 0.917 after adjudication (from BUILD_LOG; I did not
  re-run the evaluation). The separate accessory namespace and the refusal to fuzzy-match accessories are the right
  calls. This is the most reusable asset in the project.
- **The monthly panel** (`panel.py`). Reconciles exactly, explicit zeros, the March 2023 crawl-tail cutoff is
  correctly identified and flagged. Everything I did below sat on top of it without friction.
- **The event machinery** (`events.py`) as a piece of method. Placebo calibration, life-stage matching, cluster
  bootstrap and Benjamini-Hochberg are more rigour than most portfolio projects show. The conclusion it reached
  ("single events are not detectable in review data") is correct and worth stating once, clearly, as a negative result.
- **The front end and the assistant.** Product picker, timeline, channel split, rating mode, read-only DuckDB tools,
  rate limits, cost ledger, mock mode and real-model test cases. All of it transfers to a reframed product; only the
  copy and the analysis pages need to change.

### What overreaches

1. **"Demand evidence" as a title.** Review volume is validated as a demand proxy only across products at one snapshot
   (Spearman -0.71 vs the Best Sellers Rank, n=431, from BUILD_LOG). Every time-series use (the event tests, the
   portfolio growth headline "9.4x from 2013 to 2022") silently assumes the proxy holds over time. It may not: review
   propensity on Amazon changed materially over 2013 to 2023, and the mean product age at review in this data rose
   from 3.3 years (2015) to 4.15 years (2022), so more of the later volume is old products, not new demand.
2. **"What moved this product" as the product page's organising question**, when the honest answer for every one of
   1,133 products is "nothing detectable". The page is organised around a rail of verdicts that all read "No clear
   change" or "Not enough data". That is not a finding a reader can use.
3. **Pooled effects presented as "Moved".** The Findings page tags +42.5% after a sibling launch and +40% after
   refurbished appears as "Moved up" with an explanatory caveat underneath. The explanations (halo, launch timing,
   returns volume) are the more likely stories, which means the tag is wrong even though the caveat is right. A
   selection effect should not wear a verdict tag.
4. **"Cases worth a closer look" labelled "possible cannibalisation".** The method's own calibration says a 10% false
   alarm rate per event and 0 survivors after correction, so the largest drops in the list are, by construction, mostly
   the tail of noise. Labelling them cannibalisation, even with "possible", invites exactly the wrong reading.
5. **Volume as the dominant chart.** Monthly written-review counts are about 13% of star ratings (AF101, from PLAN),
   and the panel's own reconciliation shows the count is dominated by a handful of products. The rating line is the
   more meaningful series and it is currently the secondary strip.

## 2. What the data genuinely supports, column by column

I screened every field the brief lists. Verdicts: **strong** (clear, replicated signal, honest confound named),
**moderate** (real but small or noisy), **weak or none** (do not build on it).

| Idea | Fields used | Verdict | Evidence (my queries) |
|---|---|---|---|
| Complaint and failure themes by product type | review text, rating, product type | **Strong** | Section 3.1 |
| Time-to-failure stated by owners | review text | **Strong** with a reporting confound | Section 3.2 |
| Rating drift over a product's life | rating, review date, launch date | **Strong** | Section 3.3 |
| Refurbished vs new | channel, rating, text | **Strong, but the finding is the opposite of the naive one** | Section 3.4 |
| Portfolio quality trend over calendar time | rating, date, type | **Moderate**, big confound | Section 3.5 |
| Single-product quality shifts (e.g. S3501 in 2022) | rating by month, text | **Strong as case studies** | Section 3.6 |
| Successor fixed predecessor's complaints | family, launch order, text | **Moderate** | Section 3.7 |
| Verified vs unverified reviews | verified flag | **Moderate**, useful as a filter, not a finding | 3.8 |
| Helpful votes as a signal | helpful_vote | **Moderate**, useful as a weighting | 3.8 |
| Cross-product reviewers, repeat purchase | user_id | **Weak** | 3.9 |
| Sub-category BSR: what separates top from bottom | BSR snapshot | **Weak**: tautological | 3.10 |
| Spec attributes vs rating | details dict | **Weak**, one usable contrast | 3.10 |
| Colour and variant differences | child asin, Color | **None** | 3.10 |
| Discontinued vs active | Is Discontinued By Manufacturer | **None**: the field has no "Yes" values | 3.10 |
| Price vs rating | price snapshot | **None** (rho 0.02, n=414) | 3.10 |

## 3. Tests run and what they showed

All review-level numbers exclude accessories and the 18 unrelated-brand listings unless stated. "Low-star" means
rating 1 or 2. "New" means brand-store listings; "refurbished" means Amazon Renewed listings, as in the panel.

### 3.1 Complaint themes by product type (scripts 02, 07, 09)

Method: regular-expression theme tagger over lower-cased title + text of the 50,186 low-star reviews. A first pass
(script 02) was too loose on two themes ("not as described" matched any review containing "used"; the breakage
theme matched any "plastic"), so I tightened it (script 07, `T2`) and hand-read 12 random hits per theme.

Precision by eye on the tightened tagger (12 samples each): app/connectivity 10 of 12, arrived damaged or used 9,
battery/runtime 10, hose/wand crack 9, pitcher/lid/blade 10, heavy/awkward 11, noise 9, **navigation 4 of 12** (the
words "stuck" and "lost" are too broad; drop or rewrite it). The earlier samples for stopped working, leak and
brush roll read about 8, 7 and 6 of 10. Treat the theme shares below as roughly right, not exact.

Share of low-star new-unit reviews carrying each theme (types with at least 300 low-star reviews):

| Product type | n low-star | Theme 1 | Theme 2 | Theme 3 |
|---|---|---|---|---|
| Vacuum, robot | 4,953 | app/connectivity 23% | navigation 15% (loose) | stopped working 15% |
| Vacuum, upright/canister | 11,078 | stopped working 17% | heavy/awkward 10% | brush roll 9% |
| Vacuum, handheld | 3,046 | stopped working 17% | battery/runtime 13% | suction loss 7% |
| Vacuum, stick | 4,302 | stopped working 11% | heavy/awkward 8% | battery/runtime 8% |
| Steam mop | 3,537 | stopped working 17% | leak 3% | arrived damaged/used 3% |
| Coffee maker | 4,238 | leak 17% | stopped working 14% | arrived damaged/used 3% |
| Iron/steamer | 1,045 | leak 20% | stopped working 13% | arrived damaged/used 5% |
| Blender | 8,226 | stopped working 12% | leak 9% | noise 5% |
| Food processor | 1,847 | stopped working 11% | leak 6% | noise 5% |
| Air fryer | 2,042 | stopped working 12% | arrived damaged/used 4% | noise 2% |
| Multicooker | 1,139 | coating peel 6% | stopped working 5% | arrived damaged/used 5% |
| Sweeper | 818 | stopped working 11% | battery/runtime 8% | suction loss 4% |

Per product, the same tagger separates products within a type: WV201 handheld, battery 49% of its 614 low-star
reviews (looser v1 tagger); RV101 robot, app 38% of 1,692; CP301 coffee maker, leak 38% of 596; BL610 blender,
pitcher/blade 36% of 1,303; AZ1002 upright, stopped working 25% and brush roll 25% of 651.

Coverage limit: only 37.9% of low-star reviews receive at least one theme (excluding the warranty/customer-service
theme, which is 12.6% on its own). A sample of 25 untagged low-star reviews is mostly general performance ("doesn't
pick up", "not worth the money", "returned it") plus long-tail specifics (cord, filters, smell). Candidate themes
among the untagged: returned it 7.3%, not worth the money 7.2%, poor pickup or power 3.5%, filter 3.0%, clog 2.5%,
cord 2.5%. A second iteration of the tagger should reach 50 to 60% coverage; the rest is genuinely diffuse.

Helpful-vote weighting shifts the mix: weighting each low-star review by its helpful votes raises brush roll from
2.9% to 8.8%, coating peel 0.7% to 1.9%, motor burn/smell 1.7% to 3.3%, and lowers app/connectivity 2.6% to 1.6%.
Readers upvote durable hardware failures more than software gripes. That is a usable second lens, not a correction.

Main confound: reviewers self-select, and low-star reviewers over-represent failures. These are shares of
complaints, not failure rates. Say so on the page.

### 3.2 Stated time to failure (scripts 02, 07)

Among the 6,637 low-star reviews tagged "stopped working" (v1), 3,162 contain a phrase like "after 6 months", "within
a year", "lasted two weeks". Parsed to months:

- Median 6 months; 25th percentile 2 months; 75th percentile 12 months.
- 87.1% say 12 months or less; 35.7% say 3 months or less; 9.6% say 13 to 24 months.
- Medians by type: food processor 3 (n=82), handheld vacuum 4 (231), robot vacuum 4 (348), blender 5 (429), stick 6
  (213), upright 6 (940), iron 7.5 (62), air fryer 8 (127), coffee maker 10 (349), steam mop 10 (244).

Confound, and it matters: the histogram (v2, n=3,198) spikes at round numbers. 1 month 397, 6 months 329, **12 months
746 (23%)**, 24 months 193, with almost nothing at 11 or 13 months (21 and 15). People say "a year" when they mean
roughly a year. So the honest presentation is coarse bands (under 3 months, 3 to 11 months, about a year, 2 years or
more), and "a year" should not be read as a warranty cliff. Explicit "out of warranty" language appears in only 1.3%
of all low-star reviews.

Second confound: this is time since purchase as stated by the owner, from the subset who state it. Unstated failures
are probably later (people who write "after 3 weeks" are angrier and more specific than people whose vacuum faded
over four years).

### 3.3 Rating drift over a product's life (scripts 04, 06)

Method: product age at review = review date minus the panel's launch date (earliest of listed date and first review).
Within each product, compare reviews written in year 1 with reviews written in years 3 to 4. Only new-unit reviews on
units, only products with at least 100 reviews in each band, so this is 61 products.

- Mean rating change year 1 to years 3 to 4: **-0.47 stars** (median -0.42, std 0.34). 59 of 61 products fall
  (96.7%); the two exceptions are +0.05 and near zero.
- Low-star share within product: 11.1% in year 1 to 23.7% in years 3 to 4; rises in **61 of 61**.
- "Stopped working" mentions (share of all reviews, not just low-star): 2.6% to 5.0%; rises in 85% of products.
- Pooled curve, mean of within-product means by 6-month bucket: 4.41, 4.33, 4.23, 4.10, 3.94, 3.87, 3.77, 3.73,
  3.63, 3.49 over the first five years. It is monotonic.
- Removing the calendar-year mean (all products, same year) still leaves -0.37 stars, negative in 88% of products.
- By type (n products): coffee maker -0.88 (6), robot vacuum -0.68 (3), stick -0.53 (10), blender -0.47 (10),
  upright -0.40 (11), steam mop -0.38 (4), multicooker -0.33 (3), air fryer -0.20 (6).

Confounds: (a) who reviews late in a product's life is different from who reviews early (later reviewers include
owners whose unit failed and came back to say so, and buyers who chose an old model on price); (b) the launch date is
a proxy for 45% of products (first review), which compresses early life for those; (c) Amazon-wide rating behaviour
drifted downward over the same years (see 3.5). Point (a) is not a flaw for the reframed purpose: "how does owner
sentiment evolve after purchase, including returning complainers" is the question a quality team asks.

### 3.4 Refurbished vs new (scripts 03, 10)

Naive: new 4.13 (n=253,868), refurbished 4.01 (n=20,830); low-star 17.2% vs 20.3%. Product-level, 83 products with at
least 30 reviews in each channel: mean gap -0.15, refurbished lower in 66%. By type the gap looked concentrated in
kitchen (coffee maker -0.40, indoor grill -0.44, multicooker -0.27) and absent in vacuums (upright +0.03).

Then two controls:

1. Refurbished reviews skew late (2019 to 2023), when everything is rated lower. Refurbished mean rating by year:
   4.26 (2016), 4.34 (2017), 4.25 (2018), 4.16 (2019), 3.92 (2020), 3.92 (2021), 3.85 (2022).
2. **Within the same product and the same calendar year** (cells with at least 30 reviews in each channel: 59 cells,
   37 products), the mean gap is **-0.04** (median -0.02) and refurbished is lower in 54% of cells. Only multicookers
   keep a gap (-0.50, 6 cells).

So "refurbished units are rated 0.12 lower" is mostly product mix and period. It is not a refurbisher story either:
20,300 of 20,830 refurbished reviews sit on listings with no named third-party refurbisher; LYTIO (396 reviews, 4.02)
and Lutema (207, 4.18) rate the same as the rest.

What is real is fulfilment. Among low-star reviews (v1 regexes, script 03): missing parts 6.2% refurbished vs 1.9%
new; dead on arrival 6.8% vs 3.5%; "not refurbished / not new / like new" complaints 2.5% vs 0.6%; packaging 8.5% vs
5.7%. "Stopped working" is lower for refurbished (7.9% vs 12.4%), consistent with refurbished reviews being written
sooner after purchase. Verified-purchase share is higher for refurbished (93.7% vs 87.7%).

This reverses the current Findings-page story ("new-unit reviews ran 40% higher once refurbished appeared") into
something a Renewed channel manager can act on: the product is fine, the box is the problem.

### 3.5 Portfolio quality trend over calendar time (script 08)

Share of low-star new-unit reviews, all types: 10.3% (2015), 12.4%, 16.5%, 17.4%, 15.0%, 16.6%, 18.1%, **21.8%
(2022)**, 23.3% (2023 Q1). Reweighting each year to the 2016 product-type mix gives 10.3% to 22.7%, so it is not
category mix. It is within type: upright 9.2% to 25.0%, stick 5.8% to 23.9%, handheld 13.3% to 27.5%, coffee maker
15.4% to 25.5%, blender 8.8% to 17.5%. Robot vacuums sit at 26 to 33% throughout 2018 to 2022.

Partly ageing: mean product age at review rose from 3.3 to 4.15 years. But first-year-of-life reviews alone also
worsen, 7.6% (2015) to 14.0% (2022) low-star, n 2,171 and 4,900. Product-level, the mean first-year rating of
launches with at least 100 first-year reviews drifts from 4.4 to 4.6 (2012 to 2015 cohorts) to 4.16 to 4.31 (2019 to
2021 cohorts), on 7 to 21 products per cohort.

**The confound that blocks a strong claim:** Amazon reviewers in general may have become harsher over 2015 to 2022,
and there is no non-SharkNinja comparator on disk to check. The raw Home & Kitchen review file (67M lines) was
streamed once and only the SharkNinja extract kept. Extracting a comparator brand set the same way (Bissell, Hoover,
Dyson, Eureka for floor care; Instant Pot, Cuisinart, Keurig for kitchen) is free, automated, and would turn this
from "SharkNinja got worse" into either "SharkNinja got worse relative to peers" or "Amazon reviews got harsher".
Without it, present 3.5 as descriptive only.

### 3.6 Single-product shifts as case studies (scripts 09, 11)

Steam mops jumped from 15.6% low-star (2021) to 36.8% (2022). The S3501 alone: 2018 16.2%, 2019 19.7%, 2020 20.5%,
2021 20.7%, **2022 41.0% (n=691), 2023 Q1 53.5% (n=170)**. Same child ASIN (B0028MB3HM) throughout, so it is not a
listing swap. In its low-star reviews, "no steam / won't steam" rises 7% (2020) to 11% (2021) to 16% (2022) while
"stopped working after N months" falls 20% to 7%: the 2022 complaints are out-of-box, not wear-out. Twelve random
2022 low-star samples read as: never produced steam, barely got warm, missing water tank cap, arrived used. That is
the shape of a manufacturing or supplier change, and it is exactly what a quality team would want flagged.

The panel's existing "low-rating month" detector already finds months like these; what it then does (test for a
volume effect) is the wrong follow-up. The right follow-up is "what changed in the text".

### 3.7 Did the successor fix the predecessor's complaint? (scripts 04, 06)

Rating alone: 53 predecessor-successor pairs (same family and type, both with at least 100 new reviews, launch gap
6 months or more). Mean rating change -0.01, successor better in 47%. Matching life stage (first 24 months of each)
changes nothing (-0.03, 45%). **No signal** that successors rate higher.

Complaint mix is more interesting: 23 pairs with at least 60 low-star reviews each. The predecessor's top complaint
share fell in 16 of 23 successors; the overall low-star share fell in only 11 of 23. Concrete examples:
OP401 to OP101 multicooker, error-code complaints 23% to 2%; BL482 to BL480 blender, stopped working 28% to 12%;
RV850 to RV101 robot, noise 20% to 6% (but RV101 is 32% low-star overall); AV1010 to AV2501 robot, app complaints
39% to 46%, not fixed, even though the rating rose 3.57 to 4.03; AF101 to AF080 air fryer, stopped working 12% to
40% and low-star share 6.8% to 14.3%, a regression.

Confound: launch order within a family is inferred from earliest evidence, family is the letter prefix of the model
code, and "successor" is my inference, not SharkNinja's. The pairs read plausibly but a few will be siblings, not
generations. Good as a per-family page with the pairs shown; not good as a portfolio-level claim.

### 3.8 Verified flag and helpful votes (scripts 02, 05, 09)

Unverified reviews (33,543, 11.5%) average 3.49 stars vs 4.21 verified, are 32.9% low-star vs 15.3%, and carry 6.3
helpful votes on average vs 1.9. Unverified reviews are where the angriest, most-read complaints live (bought
elsewhere, came to Amazon to warn). This is a filter to expose in the UI, not a headline.

Helpful votes by star: 1-star reviews average 4.97 votes (54% have at least one), 5-star 1.75 (24%). 6.6% of 1-star
reviews have 10 or more votes. Vote-weighted theme shares are in 3.1.

### 3.9 Cross-product reviewers (scripts 04, 11)

264,901 users reviewed a unit; 7,966 (3.0%) reviewed 2 or more distinct unit products, 891 reviewed 3 or more. Of
9,566 consecutive product pairs, 24.5% are the same type (replacement or upgrade); the top transitions are
upright to upright (683), blender to blender (483), blender to upright (302). Repeat reviewing by first rating (first
review before April 2020, so at least 3 years of follow-up): 2.6% of 1-star first reviewers later reviewed another
SharkNinja unit vs 3.4% of 5-star first reviewers (n 14,941 and 98,559). Directionally sensible, but the absolute
rates are tiny because a review is a rare event. **Weak**; a footnote at most.

### 3.10 Ideas with no usable signal (scripts 01, 05)

- **Discontinued flag:** all 2,012 listings: 905 "No", 4 "false/False", 1,103 missing, **zero "Yes"**. Dead.
- **Price vs rating:** Spearman 0.02, n=414 brand-store listings with a price. Nothing.
- **BSR sub-category, top vs bottom quartile:** in every sub-category with 20 or more listings, the top quartile has
  vastly more ratings (e.g. uprights 5,775 vs 56 median) and a higher rating (4.5 vs 3.8). Rank correlates with rating
  count at -0.5 to -0.9 and with rating at -0.2 to -0.9. This says "popular, well-rated products rank well", which is
  what BSR is. One snapshot with no crawl date. Keep it only as the one-line validation it already is.
- **Spec attributes:** the only clean contrast is cordless vacuums 3.98 mean listing rating (n=77) vs corded 4.36
  (n=70), which matches the battery complaint theme and is worth one sentence. Wattage, capacity, form factor: too
  sparse and too confounded by type.
- **Colour and child-variant differences:** 47 products have 2 or more coloured brand-store listings, but 70% have a
  5x or larger ratings-count gap between variants, so the listing-level spread (median 0.4 stars) is small-sample
  noise; among variants with 100 or more ratings each (17 products) the median spread is 0.20. At review level, 77
  products have 2 or more child ASINs with 50 or more reviews; median rating spread 0.17. Nothing to report.
- **Listing richness:** image count, video count and bullet count correlate with rating count (0.39, 0.54, 0.49),
  almost certainly because best-sellers get richer listings, not the reverse.

## 4. One reframed product concept

**Working names** (owner decides): "Owner Voice", "After the Sale", "Field Report: Shark and Ninja on Amazon",
"What Breaks and When". I would pick **After the Sale**: it says the data is post-purchase and stops implying demand.

**The one-sentence question:** For each Shark and Ninja product sold on Amazon, what do owners complain about, how
soon after purchase, how does satisfaction change over the product's life, and is the refurbished channel a product
problem or a fulfilment problem?

**Who it is for:** a product-quality or consumer-insights analyst at SharkNinja (primary), a Renewed/e-commerce
channel manager (secondary), and, as a portfolio piece, an interviewer who wants to see rigorous, honest analysis of
public data. It is not for a demand planner and should say so in the first sentence.

**Headline insights the page would lead with** (all verified above; wording keeps the confound):

1. **Ratings fall 0.47 stars from year 1 to years 3 to 4 within a product, in 59 of 61 products; low-star share
   doubles from 11% to 24%.** Owner sentiment after purchase is a curve, not a number, and the curve is the same shape
   across categories. Confound stated: later reviewers include returning complainers, and Amazon-wide drift.
2. **Each category has a signature complaint.** Robots: app and connectivity (23% of low-star reviews). Handhelds:
   battery (13%). Coffee makers and irons: leaks (17%, 20%). Uprights: stopped working (17%), heavy (10%), brush roll
   (9%). Multicookers: coating peel (6%). Per-product breakdown on the product page, with example quotes.
3. **When owners say when it failed, 87% say within a year; median 6 months.** Shown in coarse bands because people
   round to 6, 12 and 24 months. By type: 3 months (food processors) to 10 months (coffee makers, steam mops).
4. **Refurbished units are not rated lower once you compare like with like (0.04 stars within product and year), but
   they arrive wrong more often: missing parts 6.2% vs 1.9%, dead on arrival 6.8% vs 3.5%.**

Plus one **case-study** module fed by the existing low-rating-month detector: "S3501 steam mop, 2022: low-star share
doubled to 41% on the same ASIN; the complaint changed from wear-out to no steam out of the box." Descriptive, no
causal verdict, with the quotes.

Optional fifth headline if the comparator extract is done: portfolio low-star share rose from 10% (2015) to 22%
(2022) within every major type. Without a comparator, keep it as a descriptive chart with the confound on it.

### Keep / redo / drop against the existing code and pages

**Keep as is**
- `pipeline/rules.py`, `clean.py`, `match.py`, `resolve_sn.py`, all eval scripts, all `data/clean/sn_listing*`,
  `sn_product*`, `sn_review.parquet`. Untouched.
- `pipeline/panel.py` and `sn_panel_month.parquet`. Add nothing; it already carries `low_ratings`, `high_ratings`,
  `verified`, `helpful_votes` per month.
- `web/` shell: router, picker, header, footer, tour scaffolding, carousel scaffolding, chat drawer, tokens, verdict
  tag CSS (repurposed, see below). `app/` service: server, limits, ledger, mock mode, tests, `find_products`,
  `get_product_timeline`, `rank_products`, `search_reviews`, `set_view`.

**Redo**
- **New pipeline step `pipeline/themes.py`**: the tightened tagger (script 07 `T2`, with `navigation` rewritten or
  dropped, plus the candidate themes from script 09: returned it, not worth the money, poor pickup, filter, clog,
  cord), applied to all reviews (not just low-star, so theme rates can be shown per star band), with the failure-time
  parser in coarse bands. Output: `sn_review_theme.parquet` (review_id, theme flags, fail_band). Add a 60-review
  hand-labelled precision file per theme under `eval/` so the page can state precision honestly, the way the matcher
  does. Deterministic, about a day of work.
- **New pipeline step `pipeline/lifecycle.py`**: per product, rating and low-star share by product-age band (0 to 6,
  7 to 12, 13 to 24, 25 to 48, 49+ months), with the calendar-year-adjusted version; per product-year, the refurbished
  gap within cell. Small.
- **Product page**: keep the timeline but make **rating the default series** and volume the strip. Replace the
  "What moved" verdict rail with three panels: complaint mix (bars, with 2 to 3 example quotes per theme, helpful-vote
  sorted, verified filter), life-cycle curve for this product against its type's pooled curve, and refurbished
  fulfilment vs product complaints where the product has both channels. Keep the low-rating-month markers on the
  chart, but clicking one opens "what changed in the text" (theme mix before vs in the flagged months), not an
  effect test.
- **Findings page**: replace the three pooled "Moved" questions with the four headline insights above, each with its
  chart and its confound sentence. Replace "Cases worth a closer look" with the case-study module (largest year-over-
  year low-star jumps on a single ASIN with at least 200 reviews in both years; S3501 is the first).
- **Portfolio page**: keep the family table; add columns for low-star share, year-1 rating, years-3-to-4 rating, top
  complaint theme. The "9.4x growth" headline should go; replace with the low-star trend chart carrying its confound.
- **Assistant**: `get_findings` and `find_cases` rewritten to the new tables; add `get_product_themes(product_id)` and
  `compare_generations(family)`; keep `search_reviews`. Re-run the 17 real-model cases plus a handful for the new
  tools (budget was about $0.32 last time).
- **Copy everywhere**: title, carousel, tour, method page. The Method page's sections on cleaning, resolution, panel
  and the review-volume proxy check stay; the event-test method moves to the appendix (below). Every page states in
  one line that the data is written Amazon reviews, self-selected, complete through March 2023.
- **Verdict tag**: keep the inspection-tag component but change the vocabulary to the new claims, e.g. "Signature
  complaint", "Falls with age", "Fulfilment issue", "Not enough reviews". Never "Moved".

**Drop**
- The per-event verdict rail as the product page's spine; the pooled "Moved up/down" tags; "possible
  cannibalisation" labels; the growth headline; the `sibling_launch` and `refurbished` event types as page content.
- The Discontinued-flag idea, price-rating, colour variants, sub-category BSR beyond the existing one-line proxy
  validation, repeat purchase (footnote at most).

### What to do with the event tests

**Demote to an appendix, keep the code, reword honestly.** One Method-page section titled something like "What we
tested and could not detect": three event types, 2,817 events, placebo-calibrated, 0 of 819 testable events survive
false-discovery control; pooled averages exist but are consistent with selection (launch timing, returns volume) and
are not shown as effects. Keep `events.py` and its parquet outputs in the repo because the placebo-calibration work is
good method evidence for an interviewer, and keep the `low_rating` detector because the case-study module reuses it.
Remove the event tables from `web/data/p/*.json` (they are most of the 9.9 MB) except the low-rating months.

### Optional, and the one thing I would add if there is a weekend

Stream the raw Home & Kitchen file again and keep a comparator set (Bissell, Hoover, Dyson, Eureka, iRobot, Keurig,
Cuisinart, Instant Pot). Same cleaning, same panel. It costs disk and a few hours on the Mac, nothing on Jarvis,
and it upgrades 3.5 and 3.3 from "SharkNinja's reviews got harsher" to a relative statement, which is the version a
SharkNinja reader actually wants. It also gives the complaint-theme shares a benchmark ("robot app complaints: 23% of
Shark low-star reviews vs X% for iRobot").

## 5. Risks and honesty notes for the rebuild

- Every theme share is a share of self-selected complaints, never a failure rate. Put that sentence on the page.
- Tagger precision must be measured and shown (hand-labelled sample per theme), as the matcher's is.
- Quotes are user-generated text; the assistant already treats tool output as data. Keep that; do not let review
  text reach the model as instructions.
- The launch date is a proxy for about 45% of products; life-cycle curves for those products start at first review,
  which is the right anchor for "time since owners started reviewing" but not for "time since release". Label it.
- No new external dependency, no LLM in the pipeline. Haiku stays where it is (the assistant), reading tables.

## Appendix: scripts in this folder and what each produced

| Script | Purpose | Key outputs used above |
|---|---|---|
| `01_listing_fields.py` | Raw `details` fields joined to products; discontinued, specs, price, richness, colour | 3.10 |
| `02_complaints.py` | First-pass tagger, failure-time parser, per-product top themes, age-band shares | 3.1, 3.2, 3.3 |
| `03_refurb_gap.py` | Refurbished vs new, naive and by type; refurbished complaint themes | 3.4 |
| `04_family_drift.py` | Within-product drift year 1 vs 3 to 4; successor pairs; cross-product reviewers | 3.3, 3.7, 3.9 |
| `05_bsr_variants.py` | BSR sub-category rank drivers; colour and child-ASIN spreads; verified flag; warranty | 3.8, 3.10 |
| `06_validate_successor.py` | Tagger samples; successor complaint mix; drift decomposition; pooled 6-month curve | 3.1, 3.3, 3.7 |
| `07_tagger_v2.py` | Tightened tagger, precision samples, failure-month histogram | 3.1, 3.2 |
| `08_calendar_trend.py` | Low-star share by type and year; composition reweighting; first-year cohorts | 3.5 |
| `09_gaps.py` | Steam-mop 2022; untagged sample; helpful-vote weighting | 3.1, 3.6, 3.8 |
| `10_refurbisher_repeat.py` | Refurbisher field; within product-year refurbished gap | 3.4 |
| `11_repeat_s3501.py` | Repeat purchase by first rating; S3501 2021 vs 2022 text; child ASIN check | 3.6, 3.9 |

Intermediate parquet files (`listing_fields.parquet`, `low_tagged.parquet`, `low_tagged_v2.parquet`) are scratch
and can be deleted.

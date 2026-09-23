# Benchmark data diagnosis for a deterministic product matcher

Read-only analysis. Data untouched under `data/raw/`. All numbers below were computed with
`explore/patterns/run_analysis.py`, which uses the reusable functions in
`explore/patterns/benchmarks_rules.py` (parsing, normalization, Jaccard, threshold tuning).
No LLM/AI API was used anywhere. Full raw results are cached at `/tmp/_bench_results.json`
(scratch, not part of the repo) if you want to re-inspect a number.

**ID-mapping direction confirmed:** in every `pairs_*.parquet`, `ltable_id` joins to
`source_source.parquet` and `rtable_id` joins to `target_target.parquet`. For Walmart-Amazon
this means source = Walmart, target = Amazon (verified by eyeballing 10 matched pairs — e.g.
ltable_id 0's title "vantec nexstar mx dual 3.5 sata hard drive enclosure" pairs with rtable_id's
"vantec nexstar mx nst-400mx-s2 dual 3.5-inch sata to usb 2.0 ... enclosure black" — same product,
Walmart's shorter listing vs. Amazon's longer one).

---

## 1. Missing-value encodings and price formats

**Finding.** Every text column across all three benchmarks encodes missing values as the
literal string `'nan'` (not empty string, not `'none'`, not whitespace). Counts of non-`'nan'`
missing forms found: 0 empty strings anywhere; 1 literal `'none'` in Walmart-Amazon
target/brand (the rest is `'nan'`). Missing-value counts by column:

| Table | Rows | Column | Missing (`'nan'`) |
|---|---|---|---|
| Walmart-Amazon source (Walmart) | 2,554 | brand | 133 |
| Walmart-Amazon source (Walmart) | 2,554 | modelno | 164 |
| Walmart-Amazon source (Walmart) | 2,554 | price | 0 |
| Walmart-Amazon target (Amazon) | 22,074 | category | 1,229 |
| Walmart-Amazon target (Amazon) | 22,074 | brand | 2 (+1 literal `'none'`) |
| Walmart-Amazon target (Amazon) | 22,074 | modelno | 6,300 |
| Walmart-Amazon target (Amazon) | 22,074 | price | 2,860 |
| Abt-Buy source (Abt) | 1,081 | price | 663 |
| Abt-Buy target (Buy) | 1,092 | description | 441 |
| Abt-Buy target (Buy) | 1,092 | price | 502 |
| Amazon-Google source (Amazon) | 1,363 | price | 199 |
| Amazon-Google target (Google) | 3,226 | manufacturer | 2,870 (89%) |

Title/name columns are never missing in any table.

**Price format.** Checked every price value in all six side-tables (`~31,390` values) with a
regex for "plain numeric string" (`^-?\d+(\.\d+)?$`). Zero values fell outside that pattern
among the non-`'nan'` values — no `$`, no thousands commas, no ranges, no trailing currency
text anywhere in these particular files (the raw scraped data was apparently already
numeric-cleaned before being packaged into this benchmark). So the "e.g. `$1,299.99`, ranges"
formats named in the task brief do not actually occur in this data; they are a real risk for
the SharkNinja/Amazon live scrape later, not for these benchmarks.

**Proposed normalization rule** (implemented as `parse_price()` in `benchmarks_rules.py`,
written defensively for the live-scrape case even though it wasn't needed here):
1. Treat `'nan'`, `''`, `'none'`, `'n/a'`, `'na'` (any case/whitespace) as missing → `None`.
2. Strip everything except digits, `.`, `,`, `-`, whitespace.
3. If the remainder matches `NUM - NUM` (a range), return the mean of the two bounds.
4. Strip thousands commas and internal spaces, cast to `float`.

**Measured parse rate:** 100% of non-missing price values parsed successfully in all six
tables (31,390 non-missing values total, 31,390 parsed). The only "loss" is the missingness
itself (rates above), not parse failure.

---

## 2. Model numbers

**Format survey (Walmart-Amazon `modelno` column).** Values are free-form: bare alphanumeric
(`elplp12`), hyphenated (`nst-400mx-s2`, `dgs-1008p`), space-hyphen mixed (`cr249-ta` vs.
`cr249 ta` — same product, two different renderings on the two sides), and slash-suffixed
variants (`hdpxt1tu2b` vs. `hd-pxt1tu2 / b`). Case is inconsistent (upper on some Amazon
listings). Trailing region/color-ish suffixes exist but are rare in this dataset (more of a
Best Buy/live-scrape concern per the color/size suffixes seen in PriceRunner, item 7).

**Normalization rule** (`normalize_modelno()`): lowercase, then strip all whitespace, hyphens,
underscores and slashes. This turns `nst-400mx-s2` and `NST-400MX-S2` and `nst 400mx s2` all
into `nst400mxs2`.

**Measured on Walmart-Amazon, all 10,242 pairs (train+valid+test combined):**

| | Matched (n=962) | Non-matched (n=9,280) |
|---|---|---|
| Either side's modelno missing | 31.8% | 36.2% |
| Normalized modelno exactly equal (of all pairs) | 51.8% | 0.0% |
| Normalized modelno exactly equal (of pairs where **both** present) | **75.9%** | **0.0%** |
| Either side's modelno appears as a token inside the other side's title | 46.0% | 0.2% |

**Reading this:** when both sides have a modelno, exact match after normalization is a
near-perfect positive signal (0.0% false-positive rate among 9,280 non-matches — literally
zero non-matched pairs share a normalized modelno). But it only fires on 68% of matched pairs
(the ones where both sides have a modelno) — recall is capped by missingness, not precision.
The title-cross-check bumps coverage: 46% of matches have one side's modelno literally
embedded in the other's title (this includes and extends the exact-equal cases, since Amazon
titles often repeat the modelno).

**Model tokens extracted from titles, Abt-Buy and Amazon-Google (no dedicated modelno
column, so tokens were extracted from `name`/`title` with a regex for alphanumeric strings
that mix letters+digits, length ≥4, excluding unit suffixes like `64gb`/`2hr`):**

| | Abt-Buy matched (n=1,028) | Abt-Buy non-matched (n=8,547) | Amazon-Google matched (n=1,167) | Amazon-Google non-matched (n=10,293) |
|---|---|---|---|---|
| Either side has zero extracted model tokens | 18.2% | 12.2% | 96.7% | 98.0% |
| Extracted token sets overlap (≥1 shared token) | **68.4%** | **1.0%** | **2.7%** | 0.6% |

Abt-Buy titles are camera/electronics-heavy with real model codes embedded (e.g. "dr-2010c"),
so the extractor works well and separates matched from non-matched cleanly (68% vs 1%
overlap). Amazon-Google titles are mostly software products ("QuickBooks 2007", "Learning
QuickBooks") with almost no alphanumeric model codes — the extractor finds nothing on 97%+ of
titles on both sides, so this signal is nearly useless for Amazon-Google specifically. That's
a real, measured finding, not a limitation of the regex: title similarity (item 4) has to
carry Amazon-Google instead.

---

## 3. Brands

**Finding.** Walmart-Amazon is the only benchmark with a dedicated brand column (Abt-Buy has
none; Amazon-Google's `manufacturer` is 89%-missing on the Google side, see item 1, so it's
not usable as a primary signal there). 1,972 unique brand strings across both sides. Spot
sample shows the normalization need is mostly case/punctuation (`"Mad Catz Inc"` vs `"mad catz
inc"`), not deep aliasing — no `hp`/`hewlett-packard`-style split was found in the 20-brand
sample or in a full-column scan for "hewlett"; brand strings in this dataset already tend to
use the short form (`casio`, `intel`, `trendnet`, `sigma`). The generic alias table in
`normalize_brand()` (lowercase, strip punctuation, collapse whitespace, plus a small
hp/hewlett-packard map for when it does appear) is a safe default for the SharkNinja case,
where "Shark" vs "SharkNinja" vs "Ninja" aliasing will matter more.

**Measured on Walmart-Amazon, all 10,242 pairs:**

| | Matched (n=962) | Non-matched (n=9,280) |
|---|---|---|
| Both sides have a brand | 95.7% | 95.2% |
| Brand equal after normalization (of both-present) | 85.9% | **77.2%** |

**Reading this:** brand is a real but weak signal exactly as the task brief predicted. 77% of
*non-matches* already agree on brand — most wrong pairs in this catalog are simply two
different products from the same brand (two different HP printers, two different Sony
cables), so brand-equal alone would still let through most false positives. It's useful as a
pre-filter/blocking key (cuts candidate space) and as one weighted feature, never as a
standalone match rule.

---

## 4. Title similarity (token Jaccard)

Method: lowercase, strip punctuation, split on whitespace, Jaccard over the token sets. Tuned
threshold by sweeping 0.01–0.99 in 0.01 steps on **train+valid only**, picking the value that
maximizes F1, then evaluated once on the untouched **test** split.

| Benchmark | Matched Jaccard (p10/p50/p90) | Non-matched Jaccard (p10/p50/p90) | Tuned threshold | Test precision | Test recall | Test F1 |
|---|---|---|---|---|---|---|
| Walmart-Amazon | 0.29 / 0.54 / 0.89 | 0.28 / 0.40 / 0.56 | **0.62** | 0.477 | 0.378 | 0.422 |
| Abt-Buy | 0.24 / 0.45 / 0.77 | 0.17 / 0.25 / 0.43 | **0.47** | 0.542 | 0.471 | 0.504 |
| Amazon-Google | 0.25 / 0.50 / 0.80 | 0.13 / 0.25 / 0.44 | **0.47** | 0.420 | 0.573 | 0.485 |

(Test split sizes: WA test n=2,049 with 193 positives; Abt-Buy n=1,916 with 206 positives;
Amazon-Google n=2,293 with 234 positives.)

**Reading this:** title Jaccard alone is a mediocre matcher on all three (F1 in the 0.42–0.50
range) because the distributions overlap heavily in the middle (p10–p90 of matched and
non-matched interleave). It's a genuinely useful *feature* to combine with modelno/brand, not
a standalone deterministic rule. Walmart-Amazon needs the highest threshold (0.62) because
Amazon's longer/keyword-stuffed titles inflate token counts and drag down Jaccard for true
matches too, while pushing up incidental overlap between different-but-related products
(same category words like "wireless", "adapter", "usb").

---

## 5. Price agreement

Relative price difference = `|p1-p2| / max(p1,p2)`, computed only where both sides parsed to a
number.

| Benchmark | Matched, both priced | Matched median rel. diff | Matched within 10% | Non-matched, both priced | Non-matched median rel. diff | Non-matched within 10% |
|---|---|---|---|---|---|---|
| Walmart-Amazon | 834/962 (86.7%) | 0.174 | 35.4% | 7,539/9,280 (81.2%) | 0.389 | 13.6% |
| Abt-Buy | 213/1,028 (20.7%) | 0.173 | 35.2% | 1,388/8,547 (16.2%) | 0.472 | 9.5% |
| Amazon-Google | 1,046/1,167 (89.6%) | 0.108 | 45.7% | 9,378/10,293 (91.1%) | 0.492 | 13.6% |

**Reading this:** matched pairs cluster much closer in price (median 11–17% apart) than
non-matched pairs (median 39–49% apart), and matched pairs are 2.5–4.7x more likely to be
within 10% of each other. But "within 10%" only catches 35–46% of true matches even at their
best — real-world price drift between retailers (sales, bundles, different pack sizes) is too
large for a hard price-equality rule. Price should be a soft/weighted signal or a sanity
filter (e.g. reject candidates >2x apart), not a primary key. Abt-Buy has the least price
coverage (only 17–21% of pairs have both prices), which limits how much this signal can carry
there regardless of its discriminative power.

---

## 6. Hard cases (Walmart-Amazon, 10 each)

### (a) Matched pairs with different modelno / low title similarity (Jaccard < 0.30, model not equal)

1. `d-link dgs-1008p 8-port gigabit ethernet poe switch` vs `d-link dgs 1008p - switch - unmanaged - 8 x 10 100 1000 - de` — models `dgs1008p` vs `1008p`; Amazon dropped the `dgs` prefix. Substring containment would catch this; exact-equal does not.
2. `read right pathkleen printer roller cleaner sheets...` vs `printer roller cleaner removes excess toner...` — Amazon's title is a generic description with no brand/model at all; only a category-level description survives. No deterministic signal short of an external catalog lookup would catch this reliably.
3. `ihome portable stereo alarm clock...gunmetal` vs `ihome ih16 portable speaker system...gray` — models `ih16g` vs `ih16gxc`: same base code, different color/SKU suffix, plus the color words disagree ("gunmetal" vs "gray") — a real product-vs-listing ambiguity, not just a data-quality issue.
4. `powermat wireless charging system...` vs `powermat one-position mat...` — models `pmm-1p-b2` vs `pmm-1pb-b2`: one character of punctuation apart, would need edit-distance or fuzzy match, not exact.
5. `clarion vx401...` vs `brand new clarion vx401...` — same model in both titles as text, but the *modelno column itself* is missing on the Amazon side; a title-scan for the Walmart modelno would resolve this one.
6. `sparco products storage file box...` vs `file storage box` — both modelno fields missing, and the Amazon title is a bare generic category phrase. Unresolvable without image/UPC data.
7. `itw dymon scrubs office wet wipes...` vs `office wipes scrubs...container itw90006` — Walmart's modelno `90006` is a substring of Amazon's `itw90006`; suffix/prefix-aware matching would help.
8. `xerox 108r00602 maintenance kit` vs `new-108r00602 maintenance kit...` — model numbers are identical (`108r00602`) once the `new-` prefix noise is stripped from the title; the modelno field itself matched correctly here — this row is really a title-Jaccard failure (extra reseller boilerplate "case pack 1 - 513983" dilutes it), not a model failure.
9. `swingline...adjustable punch` vs `new-swingline 74030 - 20-sheet light touch...` — same pattern: reseller "new-" prefix and repeated brand suppress Jaccard even though the model number `74030` matches.
10. `ape case standard dslr holster` vs `new-standard dslr holster - cl4398` — Walmart's modelno (`acpro650`) is simply wrong/different from Amazon's actual code (`cl4398`) for what is presumably the same physical product — a genuine catalog-data disagreement, not a normalization bug.

### (b) Non-matched pairs with equal modelno or very high title similarity (Jaccard > 0.60 or model equal)

1. `pc treasures clickit classic mouse black` (`07667`) vs `pc treasures clickit classic mouse - navy 07669` (`07669`) — same product line, different color variant, sequential model numbers. A naive "close model number" heuristic would falsely merge these; exact match correctly keeps them apart.
2. `belkin basic wireless n150 usb adapter` (`f7d1101`) vs `belkin n150 wireless usb adapter latest generation` (`f9l1001`) — nearly identical titles (Jaccard 0.625) but genuinely different model numbers/hardware revisions of the "same" product name.
3. `da-lite da-plex thru-the-wall...81 x...` vs `da-lite da-plex unframed...108 x 144...` — same product line, different **size** (81" vs 108"/144") baked into the title, not the model field. High Jaccard because most words overlap, but these are different SKUs — size/dimension tokens need to be treated as differentiators, not noise.
4. `guardian air step antifatigue mat 36 x 60 black` (model missing) vs `guardian 24020302 - air step...2...` (model `24030502`, and note this doesn't even match the label text `24020302` used in the source Walmart title vs the modelno field on Amazon — a likely data-entry inconsistency in the benchmark itself) — different dimensions again.
5. `human toolz 3-in-1 netbook pad galaxy black champagne` (`3n1mgc`) vs `...notebook pad galaxy black` (`3n1ngb`) — color-code suffix differs (`mgc` vs `ngb`), same base product family.
6. `da-lite da-glas self trimming rear projection screen 96 x...` vs `da-lite 27578 da-plex self trimming rear projection screen...` — different **product line** (da-glas vs da-plex) despite huge title overlap; a single differentiating word carries all the signal here, which plain Jaccard underweights.
7. `da-lite cherry veneer model b manual screen...` vs `light oak veneer model b manual screen...` — same again: only the veneer color word differs, everything else (a long shared spec boilerplate) is identical text.
8. `wausau paper astrobrights colored paper...` vs `wausau paper 60902 - exact colored paper...` — different paper *line* ("astrobrights" vs "exact"), one differentiating word.
9. `lenovo thinkpad x60 tablet digitizer pen tether 3pk` vs `thinkpad x60 tablet digitizer pen` — a 3-pack vs a single unit of the same accessory; pack-size/quantity is the only differentiator and it's easy to miss.
10. `pc treasures retractable mighty mini mouse navy` (`07221`) vs `pc treasures mighty mini mouse - retractable` (`07218`) — same pattern as #1: color/SKU variant siblings with near-identical titles.

**Pattern summary:** the dominant false-positive risk across (b) is **product-line siblings**
— same brand, same base product name, differing only in color, size, pack count, or a single
line-name word — where title Jaccard is high specifically because retailers pad titles with
shared boilerplate/spec text. A deterministic matcher needs a differentiator check (color
words, dimensions, pack-size numbers, or exact model number) layered on top of Jaccard, not
Jaccard alone. The dominant false-negative risk in (a) is reseller/marketplace title noise
("new-", "brand new", generic category-only titles from bulk uploaders) diluting an otherwise
correct model-number match.

---

## 7. PriceRunner (multi-vendor clustering)

35,311 offers, 13,233 clusters (same-product groups), 306 distinct vendors. Cluster size
distribution: median 2, p75 = 3, p90 = 5, p99 = 12, max 27, mean 2.67 — most products are seen
by only 2–3 vendors, a long tail is seen by many more (useful stress test for many-to-one
matching, as the brief expects).

**Language noise confirmed.** 608 titles (1.7% of all rows) contain a German color/spec marker
(`spacegrau`, `schwarz`, `weiß`, `grau`, `silber`, `zoll`, etc.), e.g. `"apple iphone 8 plus 64
gb spacegrau"` clustered together with `"apple iphone 8 plus 64gb silver"` and `"apple iphone
8 plus 64gb space grey"` — same cluster, same product, but color vocabulary differs by
vendor/locale. A deterministic matcher needs a small color-translation table (`spacegrau` →
`space grey`, `schwarz`→`black`, `silber`→`silver`, etc.) or must strip color words entirely
before comparing, otherwise cross-locale titles never share tokens.

**Which tokens are stable within a cluster.** Checked the 5 largest clusters directly:

- Canon IXUS 185 (27 offers): only `canon` is common to *all* titles verbatim; the numeric
  model portion `185` is present in the great majority but not literally 100% (a few titles
  drop it in favor of "digital camera silver" alone).
- Samsung UE49NU7100 (24 offers) / UE75NU7100 (23 offers): the exact-string intersection
  across all titles is **empty** — no single token appears in every title — but after
  model-token extraction, `ue49nu7100` (or its no-prefix form `nu7100`, or its suffixed form
  `ue49nu7100kxxu`) appears in 52–54% of titles in a form containing the shared numeric core;
  several titles describe the TV only generically ("49inch uhd 4k led smart tv...") with no
  model code at all.
- Canon PowerShot SX730 HS (24 offers): the short code `sx730` appears in 96% of titles — this
  is the strongest example of a stable model core across vendors.
- Apple iPhone 8 Plus 64GB (23 offers): there is **no** short alphanumeric model code at all —
  Apple's own "model numbers" (`mq8n2b/a`) appear in only 1 of 23 titles; the cluster is really
  identified by the combination of product line + capacity + color, which is exactly the case
  where a fielded attribute schema (product line, storage size, color) beats any single
  "model number" heuristic.

**Reading this for SharkNinja:** SharkNinja model numbers (e.g. `AF161`, `NC301`) behave more
like the Canon/Samsung case (a genuine compact alphanumeric code, usually present, sometimes
with an `AMZ`/region suffix per the earlier Amazon-Reviews-2023 findings in `DATA_SOURCES.md`)
than like the iPhone case, so a model-number-first strategy with a title-similarity fallback
should transfer reasonably well — but plan for a color-word normalization table regardless,
since PriceRunner shows real vendors do write colors in ways that break token overlap even in
English alone ("black" vs "charcoal black" vs "space grey").

---

## 8. ASIN-like IDs in Walmart-Amazon Amazon-side rows

Checked. The `id` column in `target_target.parquet` (the Amazon side) is a plain sequential
row index (`0, 1, 2, ...`), not an Amazon ASIN — confirmed by regex-matching against the ASIN
shape (`^B0[A-Z0-9]{8}$`): 0 of 22,074 ids match, and 0 of the `modelno` values match either.
There is no ASIN, UPC, or other externally-joinable identifier anywhere in this table — as
expected, since this is a 2015-era matching benchmark, not a live Amazon catalog dump. Any
join to a newer Amazon dataset (e.g. the Amazon-Reviews-2023 data referenced in
`DATA_SOURCES.md`) would have to go through fuzzy title/brand/model matching, i.e. the exact
methodology this whole diagnosis is building — there is no shortcut identifier to exploit.

---

## Recommended signal weighting for a deterministic matcher

Based on the measured numbers above (Walmart-Amazon used as the primary calibration set since
it has all three signal types):

1. **Exact normalized model-number match, when both sides have one → near-certain match.**
   Measured 75.9% coverage among matched pairs with both fields present, and a measured **0%**
   false-positive rate across 9,280 non-matched pairs. This should be the top-priority rule:
   if it fires, accept with high confidence; if it fires with disagreement (both present, not
   equal), that's a fairly strong signal of non-match too (item 6b examples #1, #5 show this
   holds even for very similar titles).
2. **Model number found embedded in the other side's title → strong secondary rule.** Extends
   coverage from 52% (exact-field-equal, of all pairs including missing) to 46%+ overall via
   title cross-checking (item 2), catches cases like item 6a #5 and #7 where one side's model
   field is missing but the number survives in text, at a measured 0.2–1.0% false-positive
   rate depending on benchmark.
3. **Title Jaccard as the fallback/continuous feature, not a standalone rule.** Best
   single-feature F1 measured was only 0.42–0.50 across the three benchmarks; use it to rank
   or gate candidates within a blocking set, and combine with model/brand rather than
   thresholding alone. The tuned thresholds (0.62 WA, 0.47 Abt-Buy/Amazon-Google) are
   reasonable starting points for a "maybe" band requiring human review or a secondary signal.
4. **Brand as a blocking/pre-filter key, not a match signal.** 77.2% of measured non-matches
   already share a brand — using it as a positive-match feature would flood precision; use it
   only to shrink the candidate pool before applying rules 1–3.
5. **Price as a sanity check / soft feature, weight small.** Matched pairs sit at a measured
   median 11–17% relative price difference vs. 39–49% for non-matches — directionally useful,
   but "within 10%" only covers 35–46% of true matches, so it should down-weight or veto
   candidates with extreme price gaps (e.g. >2–3x) rather than requiring close agreement.
6. **Differentiator check for color/size/pack-count words**, layered after the above. Item 6b's
   dominant failure pattern (color/size/line-name siblings with high title Jaccard) means a
   deterministic matcher needs an explicit "if these disagree, block the match regardless of
   Jaccard" rule extracting size (numeric + unit), pack count, and a small color-word list
   (including the PriceRunner German cross-locale terms, item 7) from both titles.

## Open risks

- **Model-number substring matching (item 2's "cross_in_title" check) has false-positive
  risk at scale** that wasn't stress-tested here beyond the existing benchmark pairs: a short
  model code (e.g. `1008p` in item 6a #1) could coincidentally appear inside an unrelated
  title in a much larger catalog. For SharkNinja's live catalog this needs a minimum-length
  guard and ideally a word-boundary check, not naive substring containment.
- **Amazon-Google's near-total absence of extractable model tokens (96–98% either-missing)**
  means that benchmark's matching quality has to lean almost entirely on title Jaccard
  (measured F1 only 0.485) and price; it is the weakest-performing benchmark of the three and
  is architecturally the closest analogue to a software/media catalog, not physical hardware —
  worth keeping in mind since SharkNinja is a hardware catalog and should behave more like
  Walmart-Amazon or PriceRunner's Canon/Samsung examples than like Amazon-Google.
- **Price coverage is uneven and untested for currency/unit consistency.** All three
  benchmarks' prices are already-cleaned USD floats; a live cross-retailer scrape could
  introduce multi-currency, per-unit vs. per-pack pricing, or shipping-included vs. excluded
  prices that would break the relative-difference signal silently. Not observable in this
  static benchmark data — flagged as a risk for the live-scrape phase, not measured here.
- **Threshold tuning here used train+valid combined and evaluated once on test per benchmark**,
  which is correct methodology, but the resulting thresholds (0.62 / 0.47 / 0.47) are specific
  to each benchmark's title style (e.g. Amazon's keyword-stuffed titles pushing WA's threshold
  higher) and should not be assumed to transfer directly to SharkNinja titles without
  re-tuning on a labeled SharkNinja sample once one exists.
- **PriceRunner cluster stable-token analysis was done on the 5 largest clusters only** (for
  depth of manual inspection), not the full 13,233-cluster set; the quantitative "% clusters
  with a stable numeric model core" would need a full pass if that number becomes
  load-bearing for a design decision (the qualitative pattern — code present but reformatted,
  0% for phone-style "line+capacity+color" products — was consistent across the sample checked
  and is presented as illustrative, not exhaustive).

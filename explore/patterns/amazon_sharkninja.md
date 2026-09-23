# SharkNinja Amazon 2023 dataset — pattern discovery

Read-only diagnosis. All counts below came from DuckDB SQL run locally against
`data/raw/amazon2023/meta_sharkninja.jsonl` (2,012 rows) and `reviews_sharkninja.jsonl`
(293,270 rows) with `.venv/bin/python`. No files under `data/raw/` were modified, nothing
was downloaded, no LLM/API call was used. Queries and helper functions are saved in
`explore/patterns/amazon_sharkninja_rules.py`.

Store split: `Shark` 597, `Ninja` 567, `SharkNinja` 5, `Amazon Renewed` 843 (total 2,012).

---

## 1. Model number

**Finding.** Four places carry a model-like value:

| Source | Coverage | Notes |
|---|---|---|
| `details['Item model number']` | 1,353 / 2,012 (67.2%) | cleanest source, but comes back as a JSON string that needs quote-stripping (`"AF101"` not `AF101`) |
| `details['Model Name']` | 451 / 2,012 (22.4%) | often a marketing string, not a bare code (`"Ninja FG551 Indoor Grill Air Fryer"`, `"Shark Rotator Upright Vaccum"`) |
| `details['Part Number']` | 18 / 2,012 (0.9%) | negligible coverage, mostly accessories |
| `'Model Number:'` literal inside `features[]` | 30 rows contain the phrase, but most are "CHECK YOUR MODEL NUMBER!" compatibility warnings listing OTHER products' codes, not the listing's own model — only a handful (`Model Number: 22985`, `Model Number: HV301`, `Model number : BL480UK`) are usable |
| `title`, bare regex `\b[A-Z]{1,3}[0-9]{2,5}[A-Z]{0,4}[0-9]{0,3}\b` | matches something in 1,485 / 2,012 titles overall; recovers a candidate in 471 of the 659 rows that lack `Item model number` | noisy — needs the parenthetical form below to be trustworthy |
| `title`, parenthetical form `\(([A-Z]{1,4}[0-9]{2,5}[A-Za-z0-9]{0,4})\)` | 279 / 2,012 titles match; of those, 65 are rows with NO `Item model number` at all | high precision — a model code in parens is almost always the real one |

**Disagreement.** Where both `Item model number` and `Model Name` are present (1,353 rows
have the former; a subset also has the latter), the two strings differ exactly in **284
rows**. Sampled patterns of disagreement:
- `Model Name` is a longer marketing string containing the model code (`"AV1010AE"` vs
  `"Shark AV1010AE"`) — 130+ of the 284 look like this, easy to reconcile by substring test.
- `Model Name` is a completely different, non-code string (`"WS642"` vs `"Shark"`,
  `"SP301"` vs `"Ninja"`, `"LA502"` vs `"Shark Rotator Upright Vaccum"`) — not reconcilable,
  ignore `Model Name` here.
- Trailing-suffix mismatch (`"NV351C"` vs `"NV351"`, `"CF080REF"` vs `"CF080"`) — same base
  product, different variant/condition code; this is exactly the section-2 collapse case.

`Item model number` vs `Part Number` disagree in only **2** of the 18 rows with both — not
a meaningful conflict source.

Only **884 / 1,353** titles literally contain the cleaned `Item model number` string
(`title ILIKE '%' || model || '%'`). The other 469 don't, usually because the detail field
holds a barcode-like alternate ID (`1244FC500`, `134KKW300`), an internal-only code, or a
translated/garbled value (`Handstaubsauger` — German for "hand vacuum", clearly a mis-typed
detail field, not a model number at all).

**Format buckets** (of the 1,353 `Item model number` values):

| Bucket | Count |
|---|---|
| letters+digits(+suffix), e.g. `AF101`, `NV360`, `S3501`, `NV351C` | 1,085 |
| other/freeform (garbage or multi-token) | 220 |
| pure numeric (accessory/part numbers, e.g. `22985`) | 34 |
| brand-prefixed (`"Shark UV580"`, `"Ninja NC301NV"` style, i.e. brand word inline) | 14 |

The 220 "other/freeform" values are the real problem: things like `DUO CLEAN SLIM`,
`Handstaubsauger`, `Most Shark® IONFlex™ & ION™ vacuums`, `HV322 (Factory Serviced)`,
`QH200Q Blue Renewed`, `BLZ-17212`, `CRT2SRKQS2000QCPRB` — free text, condition notes, or
compound SKUs baked into the field by the original seller.

**Proposed extraction order** (implemented in `extract_model_no()` in the rules file):
1. `details['Item model number']`, quote-stripped, upper-cased, trimmed. (67.2%)
2. If null, the parenthetical token in `title`: `\(([A-Z]{1,4}[0-9]{2,5}[A-Za-z0-9]{0,4})\)`. (+3.2%, → 70.5% combined, high confidence)
3. If still null, the bare title regex `\b[A-Z]{1,3}[0-9]{2,5}[A-Z]{0,4}[0-9]{0,3}\b`, first match only — flag as `low_confidence=True` for manual review rather than trusting outright (this step is the source of most of the "fails/ambiguous" examples below).

**Measured coverage:** steps 1+2 combined reach **1,418 / 2,012 (70.5%)** at high confidence.
Adding step 3 unverified would push nominal coverage toward ~1,889/2,012 (94%) but that
number is an **estimate**, not verified per-row — the bare regex needs a stoplist (it will
also match noise like a dimension token or a size code) before it can be trusted for linking.

**10 examples where extraction fails or is ambiguous:**
1. `Handstaubsauger` (Item model number) — not a model number at all, a mis-populated German word; title is `Shark HV300 Rocket Stick Bagless Vacuum...` so the real model (`HV300`) has to come from title, not this field.
2. `Most Shark® IONFlex™ & ION™ vacuums` — a compatibility note leaked into the model number field on an accessory listing; no usable single model number exists for this SKU.
3. `DUO CLEAN SLIM` — descriptive phrase, not a code; true model appears to be `QU202Q` per title (`Shark QU202Q DuoClean Slim Upright Vacuum (Renewed) (Red)`).
4. `HV300-REFER` — condition suffix `-REFER` (refurbished) glued onto a real code; needs a strip rule beyond the AMZ/Q/C suffix set.
5. `Coffee Maker594` — freeform, digits glued onto a generic noun; unclear what the real model is from this field alone.
6. `BLZ-17212` and `BLZ-9462` — hyphenated codes that don't match the letters+digits regex shape at all; unclear if `BLZ` is a family prefix or an internal SKU.
7. `NV356E 31` / `IX141 H` — a real-looking code plus a trailing space and stray token (looks like a truncated color/size code); ambiguous whether to keep the suffix.
8. `Shark Apex duo clean Zero- M` — brand + product name + a bare trailing letter, no numeric code at all.
9. `QH200Q Blue Renewed` — model + color + condition all concatenated with no delimiter; a naive regex will pull the correct `QH200Q` prefix but only by luck of ordering.
10. Titles like `Shark Rocket Vacuum Wall Mount` or `Ninja Foodi Pressure Cooker Family sized Pot fits up to 6 pound roasts and 3 pounds of fries` have neither an `Item model number` nor a parenthetical/bare code — these are accessories described purely by function, and legitimately have no linkable model number.

---

## 2. Retailer/variant suffixes

**Finding.** The confirmed retailer-suffix token in this corpus is **`AMZ`** (Amazon
exclusive), found in **11** `Item model number` values (e.g. `HE402AMZ`, `IX144AMZ`,
`BL770AMZ`, `CH963AMZ`, `HV343AMZ`, `HS152AMZ`, `S3504AMZ`, `AMZ493BRN`, `AMZ012BL`,
`AMZE1SRKHZ2002BK`). Note `AMZ` is not always a *suffix* — it appears fused into the middle
or front of a compound code too (`AMZ493BRN`, `AMZE1SRKHZ2002BK`), so a simple "ends with
AMZ" rule under-collapses it; treat it as a token to strip anywhere in the string.

No `WM` or `COST`/`TGT` retailer-suffix pattern was found in this dataset (0 matches for
either) — the prompt's hypothesis about WM-style suffixes doesn't hold here; that's a real
finding, not an oversight.

Distribution of a single trailing letter immediately after a digit (candidate suffix
codes) across all 1,353 `Item model number` values, counting only rows matching
`[0-9][A-Z]$`:

| Letter | Count | Letter | Count |
|---|---|---|---|
| Q | 31 | N | 5 |
| Z | 23 | L | 5 |
| H | 17 | C | 4 |
| A | 16 | R | 3 |
| D | 9 | E | 2 |
| B | 6 | M | 2 |
| T | 6 | V | 2 |
| W | 6 | P/K/G | 1 each |
| S | 6 | | |

`Q` is the standout (31 occurrences) and, from manual inspection, almost always denotes a
color/retail variant (e.g. `BL454QR`, `HV394Q`, `NV351C`/`NV351`). `Z`, `H`, `A`, `D` are
much more often a load-bearing part of the base code itself (e.g. `IZ662H`, `RV851WV`) —
**do not** strip a bare trailing letter as a general rule; only strip a known suffix token.

**Proposed base_model rule** (regex, applied to the upper-cased, quote-stripped
`Item model number`):
```
regexp_replace(upper(model_no), '(AMZ|WM|BRN|COST|TGT|REF|RB|CO|Q|C)+$', '')
```

**Measured coverage:** of 1,353 raw `Item model number` values, this collapses **1,032
distinct raw values down to 1,000 distinct base_model values** — only a 3% reduction,
because most model numbers in this corpus don't carry one of these suffix tokens. The
biggest real collapse groups (by listing count, not distinct code count):

| base_model | listings collapsed | 
|---|---|
| QB1004 | 9 |
| BL660 | 8 |
| NJ600 | 8 |
| BL480 | 7 |
| BL642 | 7 |
| CF080 | 6 |
| BL450 | 6 |
| MC750 | 6 |
| NV200 | 6 |
| BL770 | 6 |

**Example group (CF080), with risk check:** raw model numbers `CF080`, `CF080Q`,
`CF080REF` collapse to `CF080` across titles "Ninja Coffee Bar with Glass Carafe and
Auto-iQ One Touch Intelligence - CF080 (Renewed)", "... CF080Q Thermal Flavor Extraction
... (Renewed)", "Ninja Coffee Bar Auto-iQ Brewer with Glass Carafe" — this is a **safe**
collapse; all three are the same coffee maker in different color/condition.

**Flagged risky collapse:** stripping a bare trailing `C` or `Q` is safe for suffix codes
like `NV351C`→`NV351`, but the same regex would also strip the final letter off any base
code that legitimately ends in `C` or `Q` with no separate un-suffixed sibling in the
catalog (none observed among the top groups, but not exhaustively checked below the top 20 —
flag as an open risk in every case where the collapsed base_model does not also appear as
its own raw `Item model number` elsewhere in the data, since that is the actual evidence of
a real variant relationship, not a coincidence of naming).

---

## 3. Renewed listings

**Finding.**
- 843 listings carry `store == 'Amazon Renewed'`.
- 752 titles contain literally `(Renewed)` (case-insensitive).
- 67 titles contain `Certified Refurbished`.
- 0 titles contain `Renewed Premium` (that Amazon marketing term isn't used in this
  particular catalog).
- Of the 843 Renewed-store listings, **759** mention "renewed" somewhere in the title and
  **84** do not — those 84 instead use `Certified Refurbished` / `Factory Serviced` /
  `Refurb` / no marker at all (e.g. `Shark IF252 Blue`, `Shark Cordless Handvac` — plain
  titles with no refurbishment language, identifiable only via the `store` field).
- **447 / 843 (53%)** Renewed listings carry a non-null `Item model number`, meaning
  roughly half need the title-regex fallback from Section 1 to get a model number at all.

**Proposed rule:** classify a listing as Renewed if `store == 'Amazon Renewed'` OR title
matches `(?i)\(Renewed\)|Certified Refurbished|Factory Serviced|\bRefurb\b`. Using `store`
alone is both necessary and (mostly) sufficient — the title-text signal only adds value for
the rare non-Renewed-store listing that itself mentions a refurbished condition (worth a
follow-up check but not run here since it's out of scope for Section 3's specific ask).

**Linking to brand-store listings via base_model:** applying the Section 2 base_model rule
to the 447 Renewed listings with a model number, and checking whether that base_model also
appears among the `Shark`/`Ninja` (non-Renewed) listings, is the mechanism — this specific
join count was not separately re-verified as its own query in this pass (it follows
directly from combining the base_model groups already shown in Section 2, several of which
demonstrably mix a `(Renewed)` title with a non-Renewed title under the same base, e.g. the
`CF080` group above); flag this as the next concrete query to run before trusting the
Renewed→brand-store link rate as a hard number.

---

## 4. Brand normalization

**Finding.** `details['Brand']` has **310** nulls and a long tail of noisy values beyond
`Ninja` (791) and `Shark` (730): `LYTIO` (87), `Lutema` (47), `SharkNinja` (9), `SHARK` (5,
casing variant), `Lytio Ninja` (3), `SPARC LIGHTING` (3), `Unknown` (3), `Generic` (2),
`Supportiback` (2), `Aurabeam` (2), plus many singletons (`Niaja` — misspelling, `AUG`,
`Kispog`, `Zotoyi`, `MOSKILA`, `joystar`, `iSPECLE`, etc.).

Critically, **all 87 `LYTIO` and all 47 `Lutema` rows are under `store == 'Amazon Renewed'`**
— zero under `store IN ('Shark','Ninja')`. These are third-party resellers of refurbished
Shark/Ninja units whose company name landed in the `Brand` detail field, not evidence of
non-SharkNinja products contaminating the brand-store listings. Sample titles confirm this:
`LYTIO`-tagged rows are legitimate Renewed Ninja blenders and Shark vacuums
(`Ninja Profesional Blender BL454QGN...`, `Shark APEX Stick Vacuum...`).

Within the 1,164 genuine `Shark`/`Ninja`-store listings, the `Brand` field disagrees with
the store name in only **4 rows**, and all 4 are just the casing variant `SHARK` (upper
case) — not a different company. `details['Manufacturer']` is messier with casing/spacing
variants of `SharkNinja` itself (`Shark/Ninja`, `Shark\`Ninja`, `SHARKNINJA SALES CO`,
`Euro-Pro` — the pre-2008 corporate name for Shark — `Sharkninja`, `EuroPro`, `Euro Pro`)
but these are all genuinely SharkNinja entities, not outside brands.

**Classification rule proposed:**
- `is_sharkninja_brand`: `store IN ('Shark','Ninja','SharkNinja')` OR
  `upper(coalesce(d_brand,'')) IN ('SHARK','NINJA','SHARKNINJA')` OR
  `upper(coalesce(d_manufacturer,'')) ILIKE '%SHARK%' OR ... ILIKE '%NINJA%' OR ... = 'EURO-PRO'` (Euro-Pro is Shark's predecessor brand name).
- `is_accessory_or_part`: title matches `(?i)replacement|compatible with|for shark|for
  ninja|accessory|\bpart\b|filter\b` (162 of the 1,164 brand-store listings match this — see
  Section 5 for the overlap with product_type).
- `is_reseller_labeled` (informational only, not exclusionary): `d_brand` or
  `d_manufacturer` is a third-party name (`LYTIO`, `Lutema`, `Aurabeam`, etc.) — these are
  exclusively Renewed-store rows and should NOT be used to classify the underlying product
  as non-SharkNinja; the underlying appliance is still Shark/Ninja, the reseller name is
  metadata about who refurbished/resold it.

**Measured counts:** 1,164 listings are `Shark`/`Ninja`/`SharkNinja`-store (genuine
brand-store); of those, only 4 have a brand-field casing mismatch and none have a genuine
non-SharkNinja brand. 137 third-party-branded rows (LYTIO+Lutema+smaller singletons) exist
only inside the 843 Amazon Renewed rows and represent reseller identity, not product
identity.

---

## 5. Product type

**Finding.** `categories[]` last-segment gives a reasonably clean taxonomy already present
in the data (`Upright Vacuums` 320, `Countertop Blenders` 283, `Stick Vacuums & Electric
Brooms` 123, `Handheld Vacuums` 97, `Food Processors` 95, `Steam Mops` 81, `Robotic
Vacuums` 76, `Coffee Machines` 71, `Slow Cookers` 42, `Air Fryers` 41, `Electric Pressure
Cookers` 24, `Ice Cream Machines` 15, `Electric Grills` 14, `HEPA Air Purifiers` 11, plus
101 rows with no categories at all).

A title-keyword rule (see `PRODUCT_TYPE_CASE_SQL` in the rules file) classifies:

| product_type | count |
|---|---|
| blender | 426 |
| unclassified | 380 |
| vacuum-upright | 295 |
| vacuum-stick | 244 |
| vacuum-other | 147 |
| coffee maker | 101 |
| pressure cooker | 88 |
| robot vacuum | 82 |
| steam mop | 76 |
| air fryer | 57 |
| accessory/part | 51 |
| food processor | 22 |
| ice cream maker | 17 |
| grill | 13 |
| air purifier | 13 |

**Coverage:** 1,632 / 2,012 (81%) classified by title keywords alone. The 380
"unclassified" rows are mostly real, classifiable product types that just don't use the
keyword vocabulary above — slow cookers (`BRAND NEW Ninja 2-in-1 6 Quart Stove Top Digital
Slow Cooker...`), toaster ovens (`Euro-Pro TO282 4-Slice Toaster Oven`), hand mixers
(`Euro-Pro 300-Watt 6-Speed Hand Mixer`), irons (`Euro-Pro Shark Full-Sized Iron`), deep
fryers (`Ninja Professional Frying System (F300)`), plus some genuine accessories
(`Ninja Brand Premium Floor Comfort Mat`, `Ninja Express Chop` — a hand chopper, filed
under Dinnerware & Serveware in categories).

**Recommended fix:** run the title rule first, then fall back to
`categories[array_length(categories)]` (the last category segment) for anything still
`unclassified` — that segment alone resolves most of the 380 (slow cookers, toaster ovens,
mixers, irons, deep fryers all have clean category leaves per the table above). A handful
(`Ninja Express Chop`, `Shark IF252 Blue`, `Shark Cordless Handvac`) are ambiguous even with
categories and will need a small manual mapping table (title is too terse, category is
generic "Handheld Vacuums" or "Dinnerware & Serveware" which is itself a categories.jsonl
mis-tag).

---

## 6. Units

**Finding — Capacity** (`details['Capacity']`, 618 / 2,012 = 30.7% coverage): values arrive
as text with a unit word attached, not bare numbers: `72 Fluid Ounces` (75), `6 Quarts`
(36), `16 Fluid Ounces` (27), `64 Fluid Ounces` (20), `8 Quarts` (17), `2.8 Quarts` (10),
`500 Milliliters` (7), `1 Liters` (6), `10 Cups` (5), `8 Pounds` (8, a weight, not a
volume — appears on vacuums where "Capacity" means dust-cup weight capacity, not liquid
volume). Some rows even have two capacities from a multi-piece set concatenated: `72 Fluid
Ounces, 64 Fluid Ounces` (13), `72 Fluid Ounces, 16 Fluid Ounces` (7) — these need to become
a list, not a scalar.

**Finding — Wattage** (`details['Wattage']`, 590 / 2,012 = 29.3% coverage): mostly `"N
watts"` text (`1200 watts` 75, `1000 watts` 50, `1500 watts` 45 ...) but a meaningful
minority arrive as a bare decimal string with no unit word at all (`1200.00` 17, `1100.00`
9, `500.00` 6, `1500.00` 5, `1000.00` 5) — those need a second regex branch, not just
`\d+ ?watts?`.

**Finding — title-embedded units:** 130 titles contain a `Qt`/`Quart` pattern (values seen:
6, 4, 8, 6.5, 5, 10, 1, 5.5, 2, 7, plus fractional quarts like 0.66, 0.35, 0.013 which are
almost certainly Capacity leaking in from a sub-component, not the headline size); 212
titles contain a Watt pattern; 225 contain an Oz/Ounce pattern; 37 contain a Cup pattern;
15 contain a Liter pattern.

**Proposed normalization** (implemented as `capacity_to_quarts()` / `wattage_to_watts()` in
the rules file):
- Quarts: pass through as-is.
- Fluid Ounces / Ounces → divide by 32.
- Liters → divide by 0.946353.
- Milliliters → divide by 946.353.
- Cups → divide by 4.
- Pounds: **do not** fold into quarts — it's a weight-capacity unit (dust bin, food weight),
  keep as a separate `capacity_lbs` field.
- Wattage: strip `" watts"` (case-insensitive) or accept a bare `\d+(\.00)?` numeric string.
- Multi-value Capacity strings (comma-separated) should become `capacity_list`, with the
  first value treated as primary for the panel-level normalized field.

**Measured coverage:** 618/2,012 listings have a structured Capacity value and 590/2,012
have a structured Wattage value; both regexes above successfully parse every sampled top-30
value shown in the query output (no unparsed formats observed in the top 30 by frequency,
though the long tail below that was not exhaustively checked).

---

## 7. Other fields

**Price nulls by segment:**

| store | total | price null | null rate |
|---|---|---|---|
| Ninja | 567 | 367 | 65% |
| Amazon Renewed | 843 | 673 | 80% |
| SharkNinja | 5 | 4 | 80% |
| Shark | 597 | 384 | 64% |

Overall **1,428 / 2,012 (71%)** have a null price — this is a McAuley snapshot artifact
(price wasn't always captured), and Renewed listings are hit hardest, consistent with them
being long-tail/out-of-stock SKUs at scrape time.

**Date First Available:** 1,013 / 2,012 (50.3%) populated, and of those, **1,012** match the
exact format `Month D, YYYY` (e.g. `May 2, 2014`) — effectively a single format, parses
cleanly with `strptime('%B %d, %Y')`. Only one non-conforming outlier out of 1,013.

**Best Sellers Rank:** 1,197 / 2,012 (59.5%) populated. Structure is a flat JSON object
mapping category name → integer rank, usually 1–2 keys (e.g.
`{"Home & Kitchen":15711,"Disposable Coffee Filters":63}`,
`{"Amazon Renewed":197,"Stick Vacuums & Electric Brooms":90}`) — note `"Amazon Renewed"`
itself sometimes appears as a BSR *category key*, which is a handy independent confirmation
signal for Renewed-condition listings beyond the `store` field.

**Duplicate titles:** 95 distinct titles appear more than once (up to 7× for
`Ninja QB1004 Blender/Food Processor with 450-Watt Base...`). These are exact string
duplicates — almost certainly the same product listed multiple times (color/bundle
variants with an identical title, or genuine scrape duplicates) — a strong signal for
collapsing onto one product_id independent of model-number matching.

---

## 8. Reviews

**Finding.**
- 293,270 total review rows; 2,298 distinct `asin` values but only 2,006 distinct
  `parent_asin` values — confirming `asin` (child/variant) is finer-grained than
  `parent_asin` (the parent product), as expected. **140,760 / 293,270 (48%)** of reviews
  have `asin != parent_asin`, meaning nearly half of all reviews were posted against a color
  or size *variant* child ASIN and rolled up to the parent — this is the mechanism the
  panel needs to use for variant consolidation, and it's already free (no extraction
  needed, just join on `parent_asin`).
- Every review `parent_asin` (2,006 distinct) is present in meta's 2,012 distinct
  `parent_asin` values — **zero orphan review rows** (0 parent_asins in reviews but absent
  from meta).
- Exact duplicate rows: **2,656** rows share the same `(user_id, parent_asin, timestamp)`
  triple, and **2,888** rows share the same `(user_id, text)` pair — these two duplicate
  counts are close but not identical, meaning there's a modest but real duplicate-review
  problem (roughly 1% of all rows) that needs de-duplication before building the panel,
  regardless of which key you pick.
- Timestamp range: **1,028,170,522,000 ms → 1,694,507,869,715 ms**, i.e. **2002-08-01 to
  2023-09-12** — a 21-year span (McAuley 2023 snapshot legitimately includes very old
  Amazon reviews, e.g. from the Euro-Pro era).
- **Verified-purchase share: 88.45%** of all 293,270 reviews.
- Reviews landing on `Amazon Renewed` listings were joined but the raw count was not
  isolated as its own printed number in this pass — flag as a quick follow-up query
  (`SELECT count(*) FROM reviews JOIN meta USING(parent_asin) WHERE store='Amazon Renewed'`)
  before relying on it; the join itself works (zero orphans, confirmed above).
- **Reviews predating "Date First Available" (a merge-across-listings smell):** of the
  1,013 listings with a parseable Date First Available, **76** have at least one review
  timestamped *before* that date — some by over a decade (e.g. `Ninja BL770AMZ Mega Kitchen
  System` shows `Date First Available = 2021-10-19` but has a review from `2012-12-01`;
  `Euro-Pro TO282 4-Slice Toaster Oven` shows `2008-07-01` with a review from `2003-08-25`).
  This is exactly the review-merging-across-listings signature the project brief warned
  about: Amazon rolls reviews from a whole lineage of parent ASINs (old model → AMZ-exclusive
  reissue → Renewed reissue) onto whichever `parent_asin` is current, so pre-launch-date
  reviews are a real and measurable (76/1,013 = 7.5%) contamination signal, not noise.

---

## Recommended cleaning order

1. **Normalize `store`/condition first** (Section 3/4) — it's a free, 100%-populated field
   and immediately separates Renewed (843) from brand-store (1,164) from the 5 ambiguous
   `SharkNinja`-store rows, with zero ambiguity.
2. **Extract `model_no`** using the 3-step order in Section 1 (details field → parenthetical
   title → bare title regex flagged low-confidence). Do this before base_model collapsing —
   base_model is derived from model_no, not from title text directly.
3. **Collapse to `base_model`** with the Section 2 suffix-strip regex, but only accept a
   collapse as "same product" when the base_model also appears as an actual raw model
   number elsewhere in the corpus (the CF080 pattern) — don't trust the regex alone for
   codes with no sibling evidence.
4. **Classify `product_type`** (Section 5): title rule first, categories-last-segment
   fallback second, small manual map for the residual handful.
5. **Normalize units** (Section 6) — independent of product_id work, can run in parallel
   with step 3/4.
6. **Build the parent_asin/asin variant graph from reviews** (Section 8) — this is the
   highest-leverage, zero-cost linking signal (140,760 reviews already tell you asin↔
   parent_asin variant membership) and should be merged with the base_model graph from step
   3 to get the final product_id, since the two signals will disagree in places and the
   overlap is itself useful for confidence scoring.
7. **De-duplicate reviews** (2,656–2,888 duplicate rows) before building the monthly panel,
   and treat any review dated before a listing's Date First Available as evidence to
   attribute to the *product* (via product_id) rather than the specific `parent_asin` it's
   attached to, since 76 listings show direct evidence of cross-listing review inheritance.

## Open risks

- The bare-title-regex step of model_no extraction (471 additional matches) is **unverified
  at the row level** — it will need a stoplist and spot-checking before being trusted as a
  linking key; treat anything from that step as `confidence=low`.
- Base_model suffix stripping (Section 2) is a coarse regex; verified safe only for the
  cases with sibling evidence (like `CF080`/`CF080Q`/`CF080REF`). Applying it corpus-wide
  without the sibling-evidence check risks merging genuinely different products that happen
  to end in a stripped token.
- Renewed→brand-store linkage via base_model (Section 3's last bullet) was reasoned from
  the Section 2 data but **not independently re-queried and counted** — needs its own query
  before being cited as a hard number anywhere downstream.
- Reviews landing on Amazon Renewed listings (Section 8) was joined successfully but the
  count was not isolated as a standalone printed number — same caveat, quick to fix.
- Product-type classification's "unclassified" bucket (380 rows) was only spot-checked with
  a 20-row sample; the categories-fallback rule is proposed but not yet measured for its
  actual coverage improvement.
- Third-party brand names (LYTIO, Lutema, etc.) were confirmed to sit entirely within
  Amazon Renewed and not to leak into brand-store listings — but this was checked for the
  top 2 reseller brands by volume only, not the full long tail of singleton brand values.

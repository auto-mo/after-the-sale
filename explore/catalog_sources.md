# SharkNinja Catalogue Source Research
Date: 2026-09-23. Read-only web research (WebSearch + WebFetch only, no downloads/logins/forms).

## 1. ManualsLib — Shark brand pages
- URL: https://www.manualslib.com/brand/shark/vacuum-cleaner.html (also /brand/shark/ and /brand/shark-cordless/vacuum-cleaner.html)
- Contains: model number/name (e.g. "Navigator LIFT-AWAY", "APEX DuoClean AZ1000 Series"), document type (owner's manual, quick start, etc.), page count. **No launch dates, no explicit category field** (category inferred only from brand sub-page, e.g. "cordless").
- Coverage: fetched page reports "over 1,417 Shark vacuum cleaner user manuals," hundreds of distinct models, spanning old EP-series through current AI Robot/PowerDetect lines. Vacuums only on this URL — Ninja kitchen products would be a separate ManualsLib brand section (not fetched).
- Verified by fetch: yes — I fetched this URL directly and it returned a real listing (structured, consistent HTML, predictable manual URLs, alphabetical organization). This looks scrapeable in principle, though I did not test actual scraping/robots.txt compliance.
- Terms of use: not checked directly; ManualsLib is a third-party archive, not SharkNinja-operated — treat content as unofficial/unverified provenance for any given manual, though the model numbers themselves are reliable since they come from real manuals.
- Trustworthiness: Medium-high for "does this model number exist and what product family is it in," low for authoritative launch-year or category taxonomy (none provided).

## 2. SharkNinja official support site (support.sharkninja.com)
- URL tried: https://support.sharkninja.com/article/NV480-Series-Shark-Rocket-Professional-FAQs
- **Not independently verified by fetch** — WebFetch returned an empty/blank result for this URL (likely JS-rendered or blocked from fetch tooling), so I could not confirm its contents directly. Everything about this URL's content below comes only from the search snippet, not a verified fetch.
- Per search snippet only: this is SharkNinja's own official support/FAQ system, organized by model "series" (e.g. "NV480 Series"), and there is a parallel "S3601 Series Shark Professional Steam Pocket Mop — Owner's Guide" article, suggesting the whole support site is structured as one article per model-series with model numbers listed together.
- Coverage: unknown without further fetches — likely covers current and legacy Shark/Ninja product lines actively supported, but the historical/discontinued tail (pre-2015) is uncertain.
- Programmatic use: unclear; this fetch attempt suggests it may require a real browser (JS rendering), which would limit programmatic scraping via simple HTTP fetch.
- Trustworthiness: highest of any source for correctness (it is SharkNinja's own official documentation), but unverified for machine coverage/accessibility today.

## 3. SharkNinja SEC EDGAR F-1 filings (2023–2024, pre-NYSE-listing prospectuses)
- URLs: https://www.sec.gov/Archives/edgar/data/1957132/000110465923075553/tm2232060-7_f1.htm (June 2023) and https://www.sec.gov/Archives/edgar/data/1957132/000110465924035202/tm247769-4_f1.htm (2024)
- **Not independently fetched/verified** — findings below come only from WebSearch snippets of these filings, not a direct WebFetch read of the full prospectus text.
- Per search snippets: the filings describe SharkNinja's portfolio as spanning **35 household sub-categories** across cleaning, cooking, food preparation, home environment and beauty (one search) and elsewhere describe **31 subcategories** (a different search) — these two numbers are inconsistent, likely reflecting different filing dates/years or paraphrasing by the search snippet rather than a verified quote. I could not confirm the exact figure or find a specific total SKU/model count in the snippets.
- Coverage/utility: F-1 filings give category-level counts and business narrative, not a model-number list — not useful for validating individual SKUs or aliases.
- Trustworthiness: high for high-level category-count claims (SEC-filed, legally reviewed) but I have NOT verified the exact wording/number by fetching the primary document, so treat "35" vs "31" as unresolved pending a direct fetch.

## Alias questions — direct evidence found (from search snippets, not independently fetched from primary retailer pages)
- **AF100 vs AF101** (Ninja air fryer): same core unit; AF101 adds a multi-layer rack, a 20-recipe guide (vs 10) and a 2-year warranty (vs 1-year) — cosmetic/bundle variant, not a different appliance. Sources: Best Buy Q&A, GrillSay, Chefiit (snippet-only, not fetched).
- **NV480 vs NV482** (Shark Rocket Professional): both are part of the official "NV480 Series" (NV480, NV481, NV482, NV484); parts/accessories are interchangeable across the series. Specific functional difference between 480 and 482 was not found in snippets — likely a retailer-exclusive or color/bundle variant within one series. Source: support.sharkninja.com NV480 Series FAQ (snippet only — see caveat above), Walmart/EZVacuum parts listings.
- **WS642 vs WS642AE** (Shark Wandvac): WS642AE is the self-emptying variant (adds a HEPA self-empty charging base holding up to 30 days of debris); WS642 is the standard charging-dock version. Sources: Amazon listings, vacuumcleanerreviewszone.com, RTINGS (snippet-only, not fetched).
- **S3601 vs S3601D** (Shark Professional Steam Pocket Mop): same core mop; S3601D ("Deluxe") includes an extra triangular mop head and a second washable microfiber pad. Source: vacuumcleanerreviewszone.com (snippet-only, not fetched).

All four alias answers above are consistent with a general pattern: the base model number identifies one physical machine, and single-letter/short suffixes (D, AE) or adjacent numbers (480/481/482/484) typically denote accessory bundles, colorways, or a specific feature add-on (like self-empty), not a different product. None of this was verified by directly fetching a primary source page — all four came from WebSearch snippets summarizing retailer Q&A and vacuum-comparison sites, not SharkNinja's own manuals.

## Suspicious content
None encountered. No page content addressed to an AI/assistant or attempted instruction injection was found in any search snippet or fetched page during this research.

## Recommendation
No single source is a ready-made, complete, machine-readable catalogue of ~1,100 SharkNinja models with categories and launch years — none of the candidates combine full coverage, structured fields, and easy programmatic access simultaneously.
- **Best for sanity-checking raw model-number existence and rough counts:** ManualsLib's Shark brand pages — largest verified count found (1,400+ manuals), consistent HTML, directly fetched and confirmed real; but no dates/categories and Ninja kitchen products aren't covered by the URL checked.
- **Best for authoritative alias/variant resolution (e.g., confirming AF100 vs AF101 are the same base unit):** SharkNinja's own support.sharkninja.com series-FAQ pages — highest trust since it's the manufacturer, but I could not verify its content or scrapability by direct fetch this session (blank result), so treat this as a lead to re-test with a real browser, not confirmed.
- **Best for category-level sanity check (not per-model):** the SEC F-1 filings — legally vetted subcategory counts (31 or 35, unresolved which), useful only as a coarse cross-check on category breadth, not on the ~1,100 unit count or individual aliases.
Net: use ManualsLib as the primary volume/existence check, and manually spot-check aliases against support.sharkninja.com and retailer Q&A pages (Amazon/Best Buy) since no aggregator source cleanly encodes the base-model-to-variant-suffix relationship.

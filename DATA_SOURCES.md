# Data sources: what can be collected automatically (researched 2026-09-23)

The question this answers: which retailer data can we pull automatically for free or cheaply,
so the project scope can be set around real data.

Status key: **verified** = checked against the provider's own page; **reported** = from
third-party write-ups only, not yet confirmed.

## Official retailer APIs

| Source | Covers | Cost | Can we get access? | Status |
|---|---|---|---|---|
| Amazon Creators API (PA-API 5 was retired May 15, 2026) | Amazon price, rating, reviews, availability | Free | Realistically no. Requires an approved Associates account and about 10 qualifying sales in the last 30 days. Access is revoked after 30 days without sales. | Deprecation verified; the eligibility rule is reported |
| Best Buy Products API | salePrice, regularPrice, customerReviewAverage/Count, modelNumber, UPC, availability | Free | Probably. Anyone can sign up, but free email addresses (Gmail and similar) have been refused since 2016. A Babson .edu address may work. The terms say not to cache content except temporarily. | Fields and caching rule verified; email rule reported |
| Walmart affiliate API (walmart.io) | Title, price, product lookup | Free | Unlikely. Only for approved content providers with a business case. | Reported |
| Target | None. There is no official public API. The site runs on an internal API (RedSky) that people hit directly with proxies. | n/a | Not recommended. It is unofficial, blocks bots, and is scraping in all but name. | Reported |

## Third-party data providers (they collect the data; we call their API)

| Source | Covers | Cost | Notes | Status |
|---|---|---|---|---|
| SerpApi | Amazon, Walmart and Home Depot engines, plus Google Shopping and the Google Immersive Product API. The Immersive API lists every seller for one product, with price, original price and rating. | **Free: 250 searches a month (50 an hour).** Starter is $25/mo for 1,000. | The strongest free option. Google's per-product store list could handle much of the cross-retailer matching. It is not yet known whether Amazon, Target and Best Buy appear in those store lists. | Free-tier numbers verified; store coverage untested |
| Traject Data: Rainforest (Amazon), BlueCart (Walmart), RedCircle (Target) | Full product, offer, seller and review data per retailer | Paid. Pricing and trial terms not confirmed. | One vendor for all three big retailers, with consistent schemas. The spec already names Rainforest as a licensed feed. | Reported |
| Keepa | Amazon only, with deep price, rank and seller history | No free tier. The API starts around €49/mo. | Best source for Amazon history, but Amazon only and not free. | Reported |

## Free historical dataset

| Source | Covers | Notes |
|---|---|---|
| Amazon Reviews 2023 (McAuley Lab, UCSD, on Hugging Face) | Amazon only, 1996 to Sep 2023. Reviews and item metadata (price, rating) across 33 categories, including Home and Kitchen. | Free and legitimate, but frozen at 2023, Amazon only, and not live. Suits a review-text or rating-trend angle, not a current cross-retailer comparison. |

## What this means for scope

- No free, official source covers Amazon, Walmart and Target together. The only free official
  one is Best Buy, and only if a non-free email address is accepted.
- The practical free path is **SerpApi's free tier**. At 250 searches a month, about 20 SKUs
  across 3 or 4 sources is about 60 to 80 calls per snapshot, which allows roughly 3 snapshots
  a month. That is enough for a demo, not for daily tracking. The $25/mo tier allows daily runs.
- "First-party vs third-party" can mean two things, and they need different data:
  1. **Who sells the Amazon listing** (Amazon, SharkNinja, or a third-party seller). This needs
     Amazon offer and seller data, which SerpApi's Amazon engine and Rainforest provide.
  2. **SharkNinja's own site vs retailers.** This would mean scraping sharkninja.com, which is
     not recommended, although Google Shopping store lists may include it.

## Next step (proposed)

A feasibility check before any scoping. Run about 10 SerpApi calls on 3 to 5 Ninja SKUs and
record exactly which fields and retailers come back. Needs: a SerpApi account (the owner creates
it) and the key in a local `.env`.

## Checked: Amazon Reviews 2023 (run 2026-09-23)

Method: streamed the full Home and Kitchen (3.7M items) and Appliances (94K items) metadata
files and kept every item mentioning Shark or Ninja. Nothing large was saved to disk; the
extract is about 40 MB in the session scratchpad.

**What is there**
- 1,169 listings sold under the Shark or Ninja store: vacuums (about 300), small kitchen
  appliances (about 290), floor care, coffee, cookware, irons, and more. Covers the full
  catalog, not just air fryers.
- 28 Ninja air fry products (AF101, AF080, DZ201, DZ090, AF150AMZ, Foodi models, air fry
  ovens), 26 of them with a price.
- Every listing has a rating and a rating count. 414 of 1,169 have a price. About 440 have a
  model number in `details`, and the rest have it only in the title (for example "Ninja BL610 ...").
- 843 "Amazon Renewed" (refurbished) Shark and Ninja listings, which are separate listings for
  the same products.
- 86 model numbers appear on more than one listing (for example NV352 on 4 listings), and 11
  products carry Amazon-exclusive "AMZ" model suffixes (for example NC299AMZ, HE402AMZ).
- The reviews file (8.3 GB) has a timestamp and verified-purchase flag on every review, so
  rating over time and review velocity can be computed.

**What is not there**
- **No other retailer.** Amazon only.
- No seller or "sold by" field, so first-party vs third-party cannot be measured directly.
- No stock status and no search position.
- No crawl date on price. "Price at time of crawling" is sometime in 2023, not a dated snapshot.
- Almost no UPCs (2 of 1,169).

**Second-retailer datasets searched:** Hugging Face (Walmart, Target, Best Buy) and Kaggle
listings. Found nothing usable with SharkNinja products: tiny samples, store-location data, or
electronics-only matching benchmarks (Walmart-Amazon, around 2015). Paid dataset vendors
(Bright Data, about $250 per 100K records) exist but were not checked further.

## Sources
- https://affiliate-program.amazon.com/creatorsapi/docs/en-us/paapiv5-deprecation
- https://velantio.com/blog/how-to-get-amazon-creators-api-access
- https://bestbuyapis.github.io/api-documentation/
- https://apievangelist.com/2016/03/30/best-buy-will-not-issue-api-keys-to-free-email-accounts-and-wants-to-get-to-know-your-company/
- https://www.walmart.io/docs/affiliate/
- https://gist.github.com/LumaDevelopment/f2a34a202fed6ab5a7f3a31282834943
- https://serpapi.com/pricing
- https://serpapi.com/google-immersive-product-api
- https://docs.trajectdata.com/rainforestapi
- https://keepa.com/api-docs/plans-tokens.html
- https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
- https://amazon-reviews-2023.github.io/

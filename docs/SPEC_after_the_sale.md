# SPEC: "After the Sale" front end (reframe of `web/`)

The tool is being reframed from "Demand Evidence" (what moved a product's demand) to **After the Sale**: what Shark
and Ninja owners report after they buy, compared with peer brands. Background: `docs/REVIEW_FABLE.md`, `PLAN.md`
("Reframe" section), numbers in `data/clean/postpurchase_report.md`. The data contract is `web/data/*.json`, written by
`pipeline/export_web.py` (read that file; it is the source of truth for field names).

## Keep
Plain HTML/CSS/JS, no framework, no build step. Keep the shell: router, state, picker, header, footer, carousel and
tour scaffolding, chat drawer, tokens in `app.css`, charts module, sortable table behaviour, dark mode. Keep existing
visual language (Hanken Grotesk, tokens, spacing). Import URLs carry `?v=...`; leave them as they are (the owner's
stamp script rewrites them all before deploy).

## Owner's standing UI rules (hard)
- No em dashes anywhere in copy. No "X, not Y" phrasing. No emoji as icons (inline SVG or text).
- No small uppercase or monospace "eyebrow"/kicker text above headings.
- Headlines state the takeaway, not the topic.
- Colours only from tokens on `:root` (with dark-mode values). SharkNinja series = existing `--graphite`; add a
  `--peer` token for peer brands that contrasts with graphite and with the refurbished colour (#8DBBF0 / `--steel`) in
  both themes.
- Charts: square corners, no thick rounded focus ring on bars; tooltips as today.
- Footer on every page. Responsive to 375 px with no horizontal page scroll (tables may scroll inside their card).
  Visible keyboard focus on controls. Respect `prefers-reduced-motion`. Empty and error states handled.
- Every page carries one plain sentence saying the data is written Amazon reviews (self-selected), complete through
  March 2023, and that complaint shares are shares of 1 and 2-star reviews, never failure rates.

## Naming and copy
- Product name: **After the Sale**. Subtitle: "What Shark and Ninja owners report after they buy, compared with
  Bissell, Dyson, iRobot, Keurig and Instant Pot."
- Replace every "Demand Evidence", "demand", "what moved", "verdict", "cannibalisation", "event" wording in the UI.
- Carousel (intro, 3 to 4 slides, plain): what the data is (Amazon Reviews 2023, McAuley Lab UCSD; SharkNinja plus
  five peer brands); what the tool shows (complaints, when things break, ratings over a product's life, refurbished vs
  new); what it cannot show (sales, returns, failure rates, causes); then "Take the tour".
- Tour steps: picker; controls; timeline (rating is the default); "What owners report" panel; ask the assistant.
- Chat drawer suggested prompts: "What do owners complain about most on the S3501 steam mop?", "Which robot vacuum
  gets the most app complaints?", "How do Shark uprights compare with peers on brush roll complaints?", "When do Ninja
  blenders tend to stop working?", "Is refurbished worse than new for the AF101?".

## Routes
`#/` Overview, `#/product/:id`, `#/findings`, `#/method`. Remove the `#/event/...` page and its file; any old
`#/event/<pid>/<eid>` URL redirects to `#/product/<pid>`.

## Theme labels
`portfolio.themes` is the list of themes: `{key, label, group, precision?, precision_lo?, precision_hi?, precision_n?}`.
Always display `label`, never the key. Themes in `portfolio.weak_themes` are never shown. `warranty_service` is a
service theme: show it separately ("Also mentioned: warranty and service") and never rank it among product problems.

## Overview page (`#/`, replaces portfolio.js content)
1. Heading area: the product name, subtitle, and one takeaway headline built from data, e.g. "Owners of both
   SharkNinja and peer brands grow less happy as products age; where SharkNinja differs is what they complain about".
2. **Key findings** list (not a card grid): five short numbered statements with the number in bold, each linking to
   its section on `#/findings`. Build them from `portfolio.findings` (drift, trend, types biggest_gap, fail, refurb).
3. **Product types** table from `portfolio.types` (sortable): Type | 1 and 2-star share (SharkNinja vs peers, from
   `low_share`) | Biggest complaint gap (label, SharkNinja % vs peers %) | Rating change, year 1 to years 3 to 4
   (SharkNinja vs peers, with n; show "few products" when n < 5) | Typical stated time to failure (months, SN vs peers).
   A caption names the peer brands per type (`peer_brands`).
4. **Product families** table (keep today's sortable table, review volume column and default sort) plus columns
   "1 and 2-star share" (`low_share`) and "Most common complaint" (`top_theme` label; blank when null).
Drop the monthly growth chart and the "9.4x" headline.

## Product page (`#/product/:id`)
- Header as today (meta line). Controls as today; **rating is the default measure**, volume the secondary strip.
  Remove event markers and event labels from the charts (charts.js still supports `events: []`).
- Replace the right rail ("What moved") with a **"What owners report"** column, in this order:
  1. Complaint mix (`detail.themes`): when `shown` is false, say "Fewer than 30 low-star reviews, so no complaint
     breakdown." Otherwise a horizontal bar list of this product's top problem themes (by `shares`, top 6 excluding
     `warranty_service`), each bar = product share, with two small markers or a thin second/third bar for its type's
     SharkNinja average (`type_sharkninja.shares`) and peer average (`type_peers.shares`, legend names
     `type_peers.brands`). Title states the takeaway, e.g. "Leaks lead complaints, 3x the peer rate".
  2. For each entry in `themes.top`: the theme label and share, then its 1 to 2 quotes (date, star rating, "verified",
     helpful votes, excerpt), collapsed behind a disclosure after the first theme. Quotes are user text: insert with
     textContent only.
  3. **Year by year** table (`detail.years`): Year | Reviews | 1 and 2-star share | Most common complaint that year.
     Highlight rows whose low-star share rose 10 points or more over the previous year. The last year may be partial
     (2023 = January to March); label it.
  4. **Over the product's life** small line chart (`detail.lifecycle` vs `detail.lifecycle_ref`): average rating by
     age band for this product, the SharkNinja type average and the peer type average. If `detail.drift` exists, one
     sentence: "Rated X in year 1 and Y in years 3 to 4". Note when `launch_source` is a first-review proxy.
  5. **Refurbished** block only when `detail.refurb` exists: new vs refurbished rating and 1 and 2-star share; the
     same-year comparison (`refurb.cells`) when present; arrival complaint shares (missing parts, arrived damaged or
     used, not as described, dead on arrival) for both channels; up to 3 refurbished quotes.
  6. Listings disclosure (keep).
- Products without `themes` (accessories etc.): show the chart and a plain note that complaint analysis covers units only.

## Findings page (`#/findings`)
Six sections, each: takeaway headline, one chart or compact table, 2 to 3 sentences, and a "Caveat" sentence.
Anchor ids `#drift`, `#trend`, `#complaints`, `#failure`, `#refurb`, `#cases`.
1. `#drift` Ratings fall as products age, for every brand. Line chart of `findings.curve` (rating by age band,
   SharkNinja vs peers) + `findings.drift` numbers (products, mean change, how many fell, low-star year 1 vs years
   3 to 4). Caveat: later reviewers include owners whose unit failed; launch date is a proxy for some products.
2. `#trend` The rise in 1 and 2-star reviews is shared by peer brands. Two-line chart of `findings.trend` low_share by year
   (2012 to 2023, 2023 = Q1 only, dashed/hatched), SharkNinja vs peers. Caveat: equal weight per product type in both
   sets; peers are five brands, not all of Amazon.
3. `#complaints` Each category has a signature complaint. From `portfolio.types`: per type, the top 3 gaps as a dot
   or dumbbell row (SharkNinja % vs peers %). Caveat: keyword themes, precision shown on Method.
4. `#failure` When owners say it stopped working. Grouped bars of `findings.fail.bands` for "All types" (bands in the
   order Under a month, 1 to 3 months, 4 to 11 months, About a year, 2 years or more), SharkNinja vs peers, plus the
   medians by type from `findings.fail.summary`. Caveat: owners round to 6, 12 and 24 months; only reviews that state
   a time.
5. `#refurb` Refurbished units hold up; what goes wrong is on arrival. Naive vs same-product-same-year gap
   (`findings.refurb`) and the arrival bars (refurbished vs new). Caveat: refurbished reviews are fewer and later.
6. `#cases` Products whose complaints jumped in one year. List of `findings.cases`: product label (link to its page),
   type, years, low-star share before and after, peers' change that year, rising themes with labels. Caveat:
   descriptive; the data cannot say why.

## Method page (`#/method`)
Keep the data, cleaning, matching and panel sections (update wording away from demand). Add:
- **Peer brands**: which five, matched by store name, brand-store units only, same cleaning, listing level.
- **Complaint themes**: rules-based keyword tagger over review title and text; table of every theme with its measured
  precision and range (from `portfolio.themes`), sample size, and the rule "themes under 0.7 are not shown".
- **Stated time to failure**: parsed phrases like "after 6 months"; bands.
- **Appendix: what we tested and could not detect** (from `portfolio.event_appendix`): three event types (sibling
  launch, refurbished units appearing, low-rating month); 2,817 events, 819 testable; placebo false-alarm rate 10.4%
  before correction; after a false-discovery check none survives. Pooled averages existed but are consistent with
  selection (launches and refurbished units follow growth), so they are not shown as effects. Review volume tracks
  the Best Sellers Rank snapshot across products (Spearman -0.71, n = 431) but is not validated over time, which is
  why this tool makes no demand claims.

## Testing (required before you report done)
Serve `web/` with `python3 -m http.server 8765` from `web/` (kill it by exact PID when done). Check in the browser:
Overview, Findings, Method, and product pages SN-S3501, SN-AV752 (robot), SN-AF101, an accessory product, and a
product with no refurbished data; desktop and 375 px; light and dark; no console errors. Take screenshots and look at
them. Report what you checked and anything you could not fix.

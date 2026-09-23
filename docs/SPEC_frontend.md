# SPEC: Demand Evidence front end (`web/`)

Plain HTML/CSS/JS. **No framework, no build step, no npm.** Files: `web/index.html`, `web/app.css`, `web/app.js`
(ES module allowed, split into a few modules under `web/js/` if it helps). The page must work when served from a
sub-path (production: `https://apps.mohithgujjula.com/demand/`), so **every URL is relative** (`data/products.json`,
`api/chat`), never starting with `/`.

## Who it is for, and the one job
Someone who works on Shark / Ninja products picks a product and sees evidence of what moved its Amazon demand and
what did not, and can ask questions. Dominant information: the product's monthly timeline with events marked, and the
verdicts next to it. Primary action: pick a product.

## Design (approved storyboard, follow it closely)
Reference frames: `design/storyboard/*.dc.html` (static HTML; read them for exact layout, spacing, copy and tokens).
- Tokens: ink `#16191D`, graphite `#3A4048` (new units), steel `#7D9CC0` (refurbished), hairline `#D5D9DE`,
  muted text `#58606A`, tag orange `#E0661B` (events and verdicts only), paper `#F4F5F7`, hatch `#C3C9D0`, white cards.
  Define them as CSS custom properties on `:root`.
- Type (Google Fonts): Archivo 600/700 for headings, IBM Plex Sans 400/500/600 for text, IBM Plex Mono 400/500 **only**
  for chart axes, big figures and table numbers (`font-variant-numeric: tabular-nums`). **No small monospace
  "eyebrow"/meta lines anywhere** (the owner rejected them).
- Header: "Demand Evidence" wordmark · product dropdown (centre) · nav Portfolio / Product / Findings / Method ·
  "Take the tour" button · "Ask" button (opens the chat drawer).
- Footer on every page: "© 2026 Mohith Gujjula" (link https://mohithgujjula.com), "Data: Amazon Reviews 2023, McAuley Lab
  (UCSD) · complete through March 2023", links "Method and limits" and "mohithgujjula.com".
- Verdict tag (signature element): inspection-tag shape (rect with 2px/12px radius, orange 1.5px border, small punched
  circle) with the label in Plex Sans 600. Labels: **Moved**, **No clear change**, **Not enough data**. For Moved add a
  direction word: "Moved up" / "Moved down". Not enough data uses a grey (#9AA2AC) border instead of orange.
- No emoji anywhere; icons are inline stroke SVG. Radius small (3–6px). Flat, hairline borders, no gradients.
- Charts: inline SVG built in JS (no chart library). Bars for monthly reviews (new graphite, refurbished steel, stacked),
  a separate rating line strip below (months below 4.4 marked with orange dots), event markers as orange dashed lines
  with small white labels, months after 2023-03 covered by a diagonal hatch with the label "incomplete data".
  Hover/focus a month shows a tooltip (month, new, refurbished, rating). Axis numbers in Plex Mono 11px.

## Data (already generated; read-only)
- `web/data/portfolio.json`: `{complete_through, months:[{m,new,renewed}], families:[{family,type,products,reviews_new,
  reviews_renewed}], pooled:[{event_type,n_events,n_products,window,avg_effect_pct,lo_pct,hi_pct,verdict}], stats:{...},
  matcher:{...}}`
- `web/data/products.json`: array of `{id,file,title,brand,type,family,model,accessory,self_empty,bundle,launch,
  launch_source,listings,brand_store,renewed,reviews_new,reviews_renewed,rating_new,events,tested}`.
- `web/data/p/<file>.json` (use the product's `file` field; 5 products have no file because they have no reviews: show
  "No reviews for this product in the data"): `{id,title,brand,type,family,model,launch,launch_source,
  months:[{m,new,renewed,rating_new,rating_renewed}], events:[{id,type,month,detail,related,window,verdict,reason,pre_mean,
  post_mean,effect_pct,lo_pct,hi_pct,n_controls,control_tier,p_value,near_zero_after,band:[{r,m,v,lo,mid,hi}]}],
  listings:[{asin,title,segment,method,rating,ratings}]}`.
  Event `type` values: `sibling_launch`, `refurbished`, `low_rating`. Verdict values: `moved`, `no_clear_change`,
  `not_enough_data` (currently no event is `moved`; still support it).

## Pages (hash routing)
1. `#/` Portfolio: title states a real takeaway computed from the data (e.g. growth between two years), monthly stacked
   bars for all products with the hatch, then the families table (Family, Main type, Products, New-unit reviews,
   Refurbished reviews, Refurbished share); clicking a family filters the dropdown/opens its largest product.
2. `#/product/<id>` Product workspace (default product: SN-AF101): title, a plain-text meta line (model, family, launch
   date and its source, listings split, review counts, average rating), controls row:
   - **Show** checkboxes "New units" and "Refurbished" (both checked by default; unchecking one keeps the other; the last
     checked box cannot be unchecked, show a short hint),
   - **From** and **To** month selects (range = product's first month to 2023-09; months after 2023-03 are labelled
     "(incomplete)"),
   - **Volume / Rating** toggle switch (`role="switch"`),
   The chart card (title = a factual takeaway computed from the visible data, e.g. "Reviews peaked at N in Month YYYY").
   Right rail "What moved <model>": one row per event (type label, detail, date, verdict tag, change vs comparison with
   range when tested, reason in plain words, link "Open the evidence" → event page). Under it the note "Not testable with
   free data: price changes, stock-outs, sales rank and buy box." Also a short honest note:
   "Across all 819 testable events, none shows a change beyond what chance produces. See Findings for the averages
   that do hold." Listings disclosure (collapsed): the product's listings with their link method.
3. `#/event/<product_id>/<event_id>` Evidence: setup panel (event select limited to this product's events, window shown,
   comparison tier shown), headline sentence built from the numbers (never invented), verdict tag, chart of the product's
   monthly new-unit reviews from −W to +W months with the comparison band (area between lo and hi, dashed mid line), the
   event month line, stat cards (before average, after average, change vs comparison with range, number of comparison
   products and tier), cautions: tier relaxed/broad ("compared with a looser set of products"), near_zero_after
   ("fell to near zero; may be a planned discontinuation"), and for `not_enough_data` the reason. Link back to the product.
4. `#/findings` Findings (replaces "Questions"): the three questions with the pooled averages from `portfolio.pooled`
   (headline sentence per question with number and range, verdict tag, n events and products), each with the plain
   explanation of what it can and cannot mean:
   - sibling launch: older products' reviews ran higher on average after a sibling launched; more consistent with a
     family halo or launches timed when a line grows than with cannibalisation; association, not cause.
   - refurbished: new-unit reviews ran higher after refurbished units appeared; refurbished units tend to appear once a
     product has sold a lot (more returns), so this is timing, not proof that refurbished sales help.
   - low rating: volume in the 3 months after a low-rating month ran slightly lower on average.
   Then a short paragraph: single events are not detectable (0 of 819 survive the false-discovery check; fake-date test
   says a single "moved" call would be wrong about 1 time in 10).
5. `#/method` Method and limits: long page. Use the content of `design/storyboard/Method.dc.html` as the base and
   update section 6 "How a verdict is reached" and section 7 with these facts: comparison group of up to 10 products
   (same type, other family, similar life stage and prior volume; looser tiers flagged); change = difference in log change
   of monthly reviews before vs after (12-month windows; 3 months for low ratings); range = resampling plus the natural
   swing of products measured on fake event dates; Moved = change of at least 15% with the range excluding zero AND
   surviving a false-discovery check across all events; No clear change = otherwise; Not enough data = fewer than 30
   reviews before the event or fewer than 3 comparison products. Fake-date test: on 3,868 fake events the method would say
   Moved about 10% of the time without the false-discovery step. Averages across events (Findings) are the reliable
   level. Keep sections 1-5, 8, 9 as in the storyboard (numbers there are correct).

## Product dropdown (combobox)
Button showing the current product; opens a panel with a search input ("Search N products..."), filter checkboxes Units /
Accessories (units only by default), results grouped by family (family code + name of its main type) sorted by total
reviews, each row: bold model code, short name, review count (mono). Keyboard: arrows, Enter, Escape, type-to-search;
ARIA combobox/listbox pattern. Show up to 60 results with "refine your search" note.

## Chat drawer ("Ask")
Right-side drawer (420px; full width under 700px). Talks to `POST api/chat` (relative). Request:
`{"messages":[{"role":"user"|"assistant","content":str}], "view":{product_id, from, to, channels:["new","renewed"], measure:"volume"|"rating"}, "turnstile_token":null}`.
Response: `{"reply":str, "view":null|{...same shape...}, "tools":[{"name":str,"summary":str}], "limited":bool, "paused":bool, "message":str|null}`.
- When `view` is returned, apply it (navigate to the product, set dates/channels/measure) and show a chip in the chat:
  "Set: AF101 · Jan 2019–Dec 2020 · new units · rating" with an **Undo** button restoring the previous view.
- Show `tools` as a small disclosure "Based on: …" under the reply.
- `limited` → show "You have reached the message limit for now. Try again in a while."; `paused` → show the server's
  `message`, keep the rest of the tool usable.
- Suggested prompts (clickable chips that send immediately), context-aware:
  on a product page: "Show {model} from Jan 2019 to Dec 2020, new units only", "What did buyers complain about in
  {model}'s low-rating months?", "How do refurbished reviews of {model} differ from new ones?", "Why is this verdict
  'No clear change'?"; everywhere: "Which air fryers have the most refurbished reviews?", "Which product families grew
  most in 2021?", "What can't this tool tell me?".
- Chat history in memory only (not stored). Max message length 1000 characters with a counter. Render replies as plain
  text with paragraphs and simple lists (no raw HTML from the server; escape everything).
- If `api/chat` is unreachable, show "The assistant is offline right now; the rest of the tool still works."

## Guided tour
Auto-opens on first visit (flag in localStorage key `de-tour-done`, all access wrapped in try/catch); "Take the tour"
replays it. Dim the page, highlight the target element (box-shadow cut-out), card with "Step N of 7", title, text, Back /
Next / Skip, Esc closes, focus moves into the card and returns afterwards, respects `prefers-reduced-motion`. Steps:
1 product dropdown ("Pick a product"), 2 controls row ("Choose the window and what to show"), 3 timeline chart ("Read the
timeline"), 4 What moved rail ("What moved this product"), 5 an "Open the evidence" link ("See the evidence"), 6 the Ask
button ("Ask the assistant": it can answer questions the page cannot, such as what reviewers said, rank products, and set
the view for you; suggested prompts are one click), 7 the Method link ("Method and limits").

## Quality bar
- Keyboard reachable everything; visible focus ring (2px orange); ARIA on custom controls; real buttons/links/labels.
- `prefers-reduced-motion` respected. Works at 1440 and does not break at 375px (rail stacks under the chart; charts
  scroll horizontally inside their card if needed; no page-level horizontal scroll).
- Never fabricate numbers; every figure comes from the data files or the API.
- Empty and error states for: product without data file, event without band, fetch failures.
- Test locally with `python3 -m http.server` from `web/` (no API needed except the chat, which should degrade to offline).

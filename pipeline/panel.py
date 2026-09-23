"""Phase 5: monthly time panel per product, plus product events.

Owner decisions (2026-09-23):
  - Reviews dated before a listing's launch are kept at product level (carried over from another listing of it).
  - Refurbished (Amazon Renewed) reviews are a separate series ('renewed') within each product; 'new' is the rest.
Data-coverage rule: monthly volume falls from ~3,500 (2022) to 2,007 (Apr 2023) and 418 (Aug 2023) because of how
the source was crawled, so months after COMPLETE_THROUGH are flagged incomplete, not treated as real declines.
Outputs (data/clean/): sn_panel_month, sn_product_event, sn_product_summary, panel_report.md
Run: .venv/bin/python pipeline/panel.py"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
COMPLETE_THROUGH = "2023-03-01"
END = "2023-09-01"

con = duckdb.connect()
con.execute(f"CREATE VIEW review AS SELECT * FROM '{C / 'sn_review.parquet'}'")
con.execute(f"CREATE VIEW lp AS SELECT * FROM '{C / 'sn_listing_product.parquet'}'")
con.execute(f"CREATE VIEW product AS SELECT * FROM '{C / 'sn_product.parquet'}'")

con.execute("""
CREATE TABLE rv AS
SELECT lp.product_id, r.parent_asin, CASE WHEN lp.segment = 'renewed' THEN 'renewed' ELSE 'new' END AS channel,
       r.review_month, r.review_date, r.rating, r.verified_purchase, r.helpful_vote, r.before_launch
FROM review r JOIN lp USING (parent_asin)
WHERE lp.product_id IS NOT NULL
""")

# Dense grid: every (product, channel) from its first review month to END, so zero months are explicit.
con.execute(f"""
CREATE TABLE grid AS
WITH spans AS (SELECT product_id, channel, min(review_month) AS m0 FROM rv GROUP BY ALL)
SELECT s.product_id, s.channel, CAST(m AS DATE) AS month
FROM spans s, generate_series(s.m0, DATE '{END}', INTERVAL 1 MONTH) g(m)
""")

con.execute(f"""
CREATE TABLE panel AS
WITH agg AS (
  SELECT product_id, channel, review_month AS month, count(*) AS reviews, sum(rating) AS rating_sum,
         sum(verified_purchase::INT) AS verified, sum(helpful_vote) AS helpful_votes,
         sum((rating <= 2)::INT) AS low_ratings, sum((rating >= 4)::INT) AS high_ratings,
         sum(before_launch::INT) AS carried_over_reviews
  FROM rv GROUP BY ALL)
SELECT g.product_id, g.channel, g.month,
       coalesce(a.reviews, 0) AS reviews,
       a.rating_sum / nullif(a.reviews, 0) AS avg_rating,
       coalesce(a.verified, 0) AS verified, coalesce(a.helpful_votes, 0) AS helpful_votes,
       coalesce(a.low_ratings, 0) AS low_ratings, coalesce(a.high_ratings, 0) AS high_ratings,
       coalesce(a.carried_over_reviews, 0) AS carried_over_reviews,
       sum(coalesce(a.reviews, 0)) OVER w AS cum_reviews,
       sum(coalesce(a.rating_sum, 0)) OVER w / nullif(sum(coalesce(a.reviews, 0)) OVER w, 0) AS cum_avg_rating,
       g.month <= DATE '{COMPLETE_THROUGH}' AS data_complete
FROM grid g LEFT JOIN agg a USING (product_id, channel, month)
WINDOW w AS (PARTITION BY g.product_id, g.channel ORDER BY g.month ROWS UNBOUNDED PRECEDING)
ORDER BY 1, 2, 3
""")

# Product family = letter prefix of the model key (NV, AF, BL, QB...), for predecessor/successor analysis.
con.execute("""
CREATE TABLE summary AS
WITH lp_dates AS (
  SELECT product_id, min(date_first_available) AS first_available,
         min(date_first_available) FILTER (WHERE segment = 'brand_store') AS first_available_brand
  FROM lp WHERE product_id IS NOT NULL GROUP BY 1),
rvs AS (
  SELECT product_id,
         min(review_date) FILTER (WHERE channel = 'new') AS first_review_new,
         min(review_date) FILTER (WHERE channel = 'renewed') AS first_review_renewed,
         max(review_date) AS last_review,
         count(*) FILTER (WHERE channel = 'new') AS reviews_new,
         count(*) FILTER (WHERE channel = 'renewed') AS reviews_renewed,
         avg(rating) FILTER (WHERE channel = 'new') AS avg_rating_new,
         avg(rating) FILTER (WHERE channel = 'renewed') AS avg_rating_renewed
  FROM rv GROUP BY 1)
SELECT p.product_id, p.canonical_title, p.brand, p.product_type, p.maker, p.is_accessory, p.self_empty_variant,
       p.model_key, nullif(regexp_extract(p.model_key, '^([A-Z]+)\\d', 1), '') AS family,
       p.n_listings, p.n_brand_store, p.n_renewed,
       -- Earliest evidence wins: a review before the listed date means an earlier listing of the product existed.
       least(coalesce(d.first_available_brand, d.first_available), r.first_review_new, r.first_review_renewed) AS launch_date,
       CASE WHEN coalesce(d.first_available_brand, d.first_available) IS NOT NULL
                 AND coalesce(d.first_available_brand, d.first_available) <= least(r.first_review_new, r.first_review_renewed)
              THEN 'date_first_available'
            WHEN coalesce(d.first_available_brand, d.first_available) IS NOT NULL THEN 'first review (earlier than listed date)'
            WHEN r.first_review_new IS NOT NULL AND (r.first_review_renewed IS NULL OR r.first_review_new <= r.first_review_renewed) THEN 'first review (proxy)'
            ELSE 'first renewed review (proxy)' END AS launch_source,
       r.* EXCLUDE (product_id)
FROM product p LEFT JOIN lp_dates d USING (product_id) LEFT JOIN rvs r USING (product_id)
""")

con.execute("""
CREATE TABLE events AS
SELECT product_id, 'launch' AS event_type, launch_date AS event_date, launch_source AS detail FROM summary WHERE launch_date IS NOT NULL
UNION ALL SELECT product_id, 'first_review_new', first_review_new, NULL FROM summary WHERE first_review_new IS NOT NULL
UNION ALL SELECT product_id, 'first_review_renewed', first_review_renewed, 'refurbished units start appearing' FROM summary WHERE first_review_renewed IS NOT NULL
UNION ALL SELECT product_id, 'listing_added', date_first_available, parent_asin || ' (' || segment || ')'
          FROM lp WHERE product_id IS NOT NULL AND date_first_available IS NOT NULL
UNION ALL SELECT product_id, 'last_review', last_review, NULL FROM summary WHERE last_review IS NOT NULL
ORDER BY 1, 3
""")

for t, f in (("panel", "sn_panel_month"), ("events", "sn_product_event"), ("summary", "sn_product_summary")):
    con.execute(f"COPY {t} TO '{C / (f + '.parquet')}' (FORMAT parquet)")

# ---------- checks ----------
q = lambda s: con.execute(s).fetchone()
lines = []
rv_n, panel_n = q("SELECT count(*) FROM rv")[0], q("SELECT sum(reviews) FROM panel")[0]
lines.append(f"reconciliation: reviews in scope {rv_n:,}; sum of panel reviews {panel_n:,}; match = {rv_n == panel_n}")
lines.append(f"excluded reviews (listings with no product_id, i.e. unrelated brands): {q('SELECT count(*) FROM review r JOIN lp USING (parent_asin) WHERE lp.product_id IS NULL')[0]:,}")
rows, prods, zero = q("SELECT count(*), count(DISTINCT product_id), sum((reviews = 0)::INT) FROM panel")
lines.append(f"panel rows {rows:,} across {prods:,} products; zero-review months explicit: {zero:,}")
gaps = q("""SELECT count(*) FROM (SELECT product_id, channel, month, lag(month) OVER (PARTITION BY product_id, channel ORDER BY month) pm FROM panel)
            WHERE pm IS NOT NULL AND month <> pm + INTERVAL 1 MONTH""")[0]
lines.append(f"missing months inside any series: {gaps}")
lines.append("channel split: " + ", ".join(f"{c} {n:,} reviews" for c, n in con.execute("SELECT channel, sum(reviews) FROM panel GROUP BY 1").fetchall()))
lines.append(f"carried-over reviews (dated before their listing launched), kept at product level: {q('SELECT sum(carried_over_reviews) FROM panel')[0]:,}")
lines.append(f"data complete through {COMPLETE_THROUGH[:7]}; later months flagged data_complete = false (crawl tail)")
lines.append("launch_source: " + ", ".join(f"{s} {n:,}" for s, n in con.execute("SELECT launch_source, count(*) FROM summary GROUP BY 1 ORDER BY 2 DESC").fetchall()))
lines.append(f"products with a model family: {q('SELECT count(*) FROM summary WHERE family IS NOT NULL')[0]:,}; distinct families {q('SELECT count(DISTINCT family) FROM summary')[0]}")
lines.append(f"launch later than first review (should be 0): {q("SELECT count(*) FROM summary WHERE launch_date > least(coalesce(first_review_new, DATE '2099-01-01'), coalesce(first_review_renewed, DATE '2099-01-01'))")[0]}")
lines.append(f"events: " + ", ".join(f"{e} {n:,}" for e, n in con.execute("SELECT event_type, count(*) FROM events GROUP BY 1 ORDER BY 2 DESC").fetchall()))
print("\n".join(lines))
(C / "panel_report.md").write_text("# Time panel report (pipeline/panel.py)\n\n" + "\n".join(f"- {l}" for l in lines) + "\n")

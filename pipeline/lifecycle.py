"""Post-purchase analysis tables: how ratings change over a product's life, how SharkNinja compares with peer brands in
the same product type, what owners complain about, when they say it failed, the refurbished gap, and single-product
case studies. Deterministic; descriptive only (no causal claims).

Definitions
- Unit review: a review of a unit (not an accessory, bundle or unclassified listing). SharkNinja "new" = brand-store
  listings; "refurbished" = Amazon Renewed listings. Comparators are brand-store units of Bissell, Dyson, iRobot,
  Keurig and Instant Pot (pipeline/comparators.py).
- Low-star: rating 1 or 2.
- Product age at review: months from the product's launch (earliest listed date or first review) to the review.
- Drift: within a product, mean rating in years 3 to 4 of its life minus year 1, for products with at least MIN_BAND
  reviews in both. Averaged with each product weighted equally.
- Data are complete through 2023-03; later months are dropped here.

In:  data/clean/sn_*.parquet, cmp_*.parquet, *_review_theme.parquet
Out: data/clean/pq_*.parquet (one table per analysis; pq_review = the review-level table, no text) and data/clean/postpurchase_report.md
Run: .venv/bin/python pipeline/lifecycle.py"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from themes import BAND_ORDER, GROUPS, LABELS, THEMES, WEAK_THEMES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
END = "2023-04-01"
MIN_BAND = 100
AGE_BANDS = [(0, 6, "0 to 6 months"), (6, 12, "7 to 12 months"), (12, 24, "Year 2"), (24, 48, "Years 3 to 4"),
             (48, 999, "Year 5+")]
SHOWN = [k for k in THEMES if k not in WEAK_THEMES]
con = duckdb.connect()
out_lines = []


def log(s=""):
    print(s)
    out_lines.append(s)


# ---------------- one long review table: SharkNinja (new + refurbished) and comparators ----------------
theme_cols = ", ".join(f"t.{k}" for k in THEMES)
con.execute(f"""
CREATE TABLE rv AS
SELECT r.review_id, 'SharkNinja' AS brand_set, s.brand, lp.product_id AS unit_id, coalesce(s.model_key, left(s.canonical_title, 50)) AS unit_label,
       s.product_type, CASE WHEN lp.segment = 'renewed' THEN 'refurbished' ELSE 'new' END AS channel,
       r.asin, r.review_date, r.rating, r.verified_purchase, r.helpful_vote, s.launch_date,
       {theme_cols}, t.fail_months, t.fail_band
FROM '{C / "sn_review.parquet"}' r
JOIN '{C / "sn_listing_product.parquet"}' lp USING (parent_asin)
JOIN '{C / "sn_product_summary.parquet"}' s USING (product_id)
JOIN '{C / "sn_review_theme.parquet"}' t USING (review_id)
WHERE s.maker <> 'unrelated' AND NOT s.is_accessory AND s.product_type NOT IN ('bundle', 'unclassified', 'accessory/part')
  AND NOT starts_with(lp.product_id, 'SN-B-') AND r.review_date < DATE '{END}'
UNION ALL
SELECT r.review_id, 'Peers' AS brand_set, r.brand, r.parent_asin AS unit_id, left(l.title, 60) AS unit_label,
       r.product_type, 'new' AS channel, r.parent_asin AS asin, r.review_date, r.rating, r.verified_purchase,
       r.helpful_vote, l.launch_date, {theme_cols}, t.fail_months, t.fail_band
FROM '{C / "cmp_review.parquet"}' r
JOIN '{C / "cmp_listing.parquet"}' l USING (parent_asin)
JOIN '{C / "cmp_review_theme.parquet"}' t USING (review_id)
WHERE r.review_date < DATE '{END}'
""")
con.execute("""ALTER TABLE rv ADD COLUMN age_m INTEGER; UPDATE rv SET age_m = greatest(0, date_diff('month', launch_date, review_date));
               ALTER TABLE rv ADD COLUMN yr INTEGER; UPDATE rv SET yr = year(review_date);
               ALTER TABLE rv ADD COLUMN low INTEGER; UPDATE rv SET low = (rating <= 2)::INT""")
band_case = "CASE " + " ".join(f"WHEN age_m < {hi} THEN '{name}'" for lo, hi, name in AGE_BANDS) + " END"
con.execute(f"ALTER TABLE rv ADD COLUMN age_band VARCHAR; UPDATE rv SET age_band = {band_case}")
con.execute(f"COPY rv TO '{C / 'pq_review.parquet'}' (FORMAT parquet)")
n = con.execute("SELECT brand_set, channel, count(*), count(DISTINCT unit_id) FROM rv GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
log("# Post-purchase analysis report\n")
log("Unit reviews in scope (complete through March 2023): " + "; ".join(f"{a} {b} {c:,} reviews on {d:,} units" for a, b, c, d in n))
# Types where both sets have enough to compare
types = con.execute("""SELECT product_type FROM rv WHERE channel = 'new' GROUP BY 1
                       HAVING count(*) FILTER (WHERE brand_set = 'SharkNinja') >= 2000
                          AND count(*) FILTER (WHERE brand_set = 'Peers') >= 2000 ORDER BY 1""").df().product_type.tolist()
log(f"Product types with at least 2,000 new-unit reviews in both sets: {', '.join(types)}")

# ---------------- 1. drift within product: year 1 vs years 3 to 4 ----------------
drift = con.execute(f"""
SELECT brand_set, brand, unit_id, any_value(unit_label) AS unit_label, product_type,
       count(*) FILTER (WHERE age_m < 12) AS n1, avg(rating) FILTER (WHERE age_m < 12) AS r1,
       avg(low) FILTER (WHERE age_m < 12) AS l1,
       count(*) FILTER (WHERE age_m BETWEEN 24 AND 47) AS n3, avg(rating) FILTER (WHERE age_m BETWEEN 24 AND 47) AS r3,
       avg(low) FILTER (WHERE age_m BETWEEN 24 AND 47) AS l3
FROM rv WHERE channel = 'new' GROUP BY 1, 2, 3, 5
""").df()
drift = drift[(drift.n1 >= MIN_BAND) & (drift.n3 >= MIN_BAND)].copy()
drift["change"] = drift.r3 - drift.r1
drift.to_parquet(C / "pq_drift.parquet", index=False)
log("\n## 1. Ratings over a product's life (year 1 vs years 3 to 4, same product)")
for bs, g in drift.groupby("brand_set"):
    log(f"- {bs}: {len(g)} products; mean change {g.change.mean():+.2f} stars (median {g.change.median():+.2f}); "
        f"fell in {(g.change < 0).sum()} of {len(g)}; low-star share {g.l1.mean():.1%} -> {g.l3.mean():.1%}")
for t in types:
    s = drift[drift.product_type == t].groupby("brand_set").change.agg(["count", "mean"])
    log(f"  - {t}: " + "; ".join(f"{bs} {r['mean']:+.2f} (n={int(r['count'])})" for bs, r in s.iterrows()))

# Pooled curve: mean of within-product means by age band, products weighted equally, units with >= 30 reviews in band
curve = con.execute("""
WITH u AS (SELECT brand_set, product_type, unit_id, age_band, count(*) AS n, avg(rating) AS r, avg(low) AS l
           FROM rv WHERE channel = 'new' GROUP BY 1, 2, 3, 4 HAVING count(*) >= 30)
SELECT brand_set, product_type, age_band, count(*) AS units, avg(r) AS rating, avg(l) AS low_share FROM u GROUP BY 1, 2, 3
UNION ALL
SELECT brand_set, 'All types', age_band, count(*), avg(r), avg(l) FROM u GROUP BY 1, 3
""").df()
curve["band_order"] = curve.age_band.map({name: i for i, (_, _, name) in enumerate(AGE_BANDS)})
curve.sort_values(["brand_set", "product_type", "band_order"]).to_parquet(C / "pq_curve.parquet", index=False)

# ---------------- 2. calendar trend: low-star share by year, same types in both sets ----------------
trend = con.execute(f"""
SELECT brand_set, yr, product_type, count(*) AS n, avg(low) AS low_share, avg(rating) AS rating,
       avg(low) FILTER (WHERE age_m < 12) AS low_share_year1, count(*) FILTER (WHERE age_m < 12) AS n_year1
FROM rv WHERE channel = 'new' AND product_type IN ({", ".join(f"'{t}'" for t in types)}) AND yr BETWEEN 2012 AND 2023
GROUP BY 1, 2, 3
""").df()
# Type-mix-neutral series: each year reweighted to equal weight per type present in both sets
tw = (trend[trend.n >= 100].groupby(["brand_set", "yr"])
      .agg(low_share=("low_share", "mean"), rating=("rating", "mean"), types=("product_type", "count")).reset_index())
trend.to_parquet(C / "pq_trend_type.parquet", index=False)
tw.to_parquet(C / "pq_trend.parquet", index=False)
log("\n## 2. Low-star share by year, new units, types in both sets (equal weight per type, cells >= 100 reviews)")
piv = tw.pivot(index="yr", columns="brand_set", values="low_share")
for y, r in piv.iterrows():
    log(f"- {y}: " + "; ".join(f"{c} {v:.1%}" for c, v in r.items() if pd.notna(v)))

# ---------------- 3. complaint themes: share of low-star new-unit reviews ----------------
def theme_shares(where, by):
    cols = ", ".join(f"avg({k}::INT) AS {k}" for k in THEMES)
    return con.execute(f"SELECT {by}, count(*) AS n_low, {cols} FROM rv WHERE low = 1 AND {where} GROUP BY {by}").df()


th_type = theme_shares("channel = 'new'", "brand_set, product_type")
th_unit = theme_shares("channel = 'new' AND brand_set = 'SharkNinja'", "unit_id")
th_type.to_parquet(C / "pq_theme_type.parquet", index=False)
th_unit.to_parquet(C / "pq_theme_unit.parquet", index=False)
cov = con.execute(f"""SELECT brand_set, avg(({" OR ".join(k for k in SHOWN if k != "warranty_service")})::INT)
                      FROM rv WHERE low = 1 AND channel = 'new' GROUP BY 1""").fetchall()
log("\n## 3. Complaint themes (share of low-star new-unit reviews)")
log("Coverage (at least one product theme): " + "; ".join(f"{a} {b:.1%}" for a, b in cov))
for t in types:
    rows = th_type[th_type.product_type == t].set_index("brand_set")
    if "SharkNinja" not in rows.index:
        continue
    sn = rows.loc["SharkNinja", SHOWN].drop("warranty_service").astype(float).sort_values(ascending=False).head(4)
    pe = rows.loc["Peers"] if "Peers" in rows.index else None
    log(f"- {t} (SharkNinja n={int(rows.loc['SharkNinja', 'n_low']):,}"
        + (f", peers n={int(pe['n_low']):,}" if pe is not None else "") + "): "
        + "; ".join(f"{LABELS[k]} {v:.0%}" + (f" vs {pe[k]:.0%}" if pe is not None else "") for k, v in sn.items()))

# ---------------- 4. stated time to failure ----------------
fb = con.execute("""SELECT brand_set, product_type, fail_band, count(*) AS n, median(fail_months) AS med
                    FROM rv WHERE fail_band IS NOT NULL AND channel = 'new' GROUP BY GROUPING SETS ((brand_set, product_type, fail_band), (brand_set, fail_band))""").df()
fb["product_type"] = fb.product_type.fillna("All types")
fb.to_parquet(C / "pq_fail_band.parquet", index=False)
fmed = con.execute("""SELECT brand_set, product_type, count(*) AS n,
                             median(fail_months) AS median_months, avg((fail_months < 12)::INT) AS within_year,
                             avg((fail_months < 4)::INT) AS within_3m
                      FROM rv WHERE fail_band IS NOT NULL AND channel = 'new' GROUP BY GROUPING SETS ((brand_set, product_type), (brand_set))""").df()
fmed["product_type"] = fmed.product_type.fillna("All types")
fmed.to_parquet(C / "pq_fail_summary.parquet", index=False)
log("\n## 4. Stated time to failure (low or any star 'stopped working' reviews that name a time)")
for _, r in fmed[fmed.product_type == "All types"].iterrows():
    log(f"- {r.brand_set}: n={r.n:,}; median {r.median_months:.0f} months; under a year {r.within_year:.0%}; "
        f"under 4 months {r.within_3m:.0%}")
for t in types:
    s = fmed[fmed.product_type == t]
    log(f"  - {t}: " + "; ".join(f"{r.brand_set} {r.median_months:.0f} mo (n={r.n})" for _, r in s.iterrows()))

# ---------------- 5. refurbished vs new (SharkNinja) ----------------
cells = con.execute("""
SELECT unit_id, yr, avg(rating) FILTER (WHERE channel = 'refurbished') AS r_ref, count(*) FILTER (WHERE channel = 'refurbished') AS n_ref,
       avg(rating) FILTER (WHERE channel = 'new') AS r_new, count(*) FILTER (WHERE channel = 'new') AS n_new
FROM rv WHERE brand_set = 'SharkNinja' GROUP BY 1, 2
""").df()
cells = cells[(cells.n_ref >= 30) & (cells.n_new >= 30)].copy()
cells["gap"] = cells.r_ref - cells.r_new
naive = con.execute("""SELECT avg(rating) FILTER (WHERE channel='refurbished') - avg(rating) FILTER (WHERE channel='new')
                       FROM rv WHERE brand_set = 'SharkNinja'""").fetchone()[0]
arr = theme_shares("brand_set = 'SharkNinja'", "channel")
arr.to_parquet(C / "pq_refurb_themes.parquet", index=False)
cells.to_parquet(C / "pq_refurb_cells.parquet", index=False)
log("\n## 5. Refurbished vs new (SharkNinja)")
log(f"- Naive gap {naive:+.2f} stars. Same product and year: {len(cells)} cells on {cells.unit_id.nunique()} products, "
    f"mean {cells.gap.mean():+.2f} (median {cells.gap.median():+.2f}); refurbished lower in {(cells.gap < 0).mean():.0%}")
a = arr.set_index("channel")
for k in ["missing_parts", "dead_on_arrival", "arrived_damaged_used", "not_as_described", "stopped_working"]:
    log(f"- {LABELS[k]}: refurbished {a.loc['refurbished', k]:.1%} vs new {a.loc['new', k]:.1%} of low-star reviews")

# ---------------- 6. case studies: biggest year-over-year rise in low-star share on one product ----------------
yr = con.execute("""SELECT unit_id, any_value(unit_label) AS unit_label, any_value(product_type) AS product_type, yr,
                           count(*) AS n, avg(low) AS low_share
                    FROM rv WHERE brand_set = 'SharkNinja' AND channel = 'new' GROUP BY 1, 4""").df()
yr = yr.sort_values(["unit_id", "yr"])
yr["prev_n"] = yr.groupby("unit_id").n.shift()
yr["prev_low"] = yr.groupby("unit_id").low_share.shift()
yr["prev_yr"] = yr.groupby("unit_id").yr.shift()
cand = yr[(yr.prev_yr == yr.yr - 1) & (yr.n >= 150) & (yr.prev_n >= 150) & (yr.yr <= 2022)].copy()
cand["jump"] = cand.low_share - cand.prev_low
# Baseline: how much the peer brands' low-star share moved that year in the same type (all peer types when the type
# has no peer data). Using peers keeps the product itself out of its own baseline (the S3501 alone is most steam mops).
pt = trend[(trend.brand_set == "Peers") & (trend.n >= 100)].set_index(["product_type", "yr"]).low_share
pa = tw[tw.brand_set == "Peers"].set_index("yr").low_share
def base(t, y):
    v = pt.get((t, y), np.nan) - pt.get((t, y - 1), np.nan)
    return v if pd.notna(v) else pa.get(y, np.nan) - pa.get(y - 1, np.nan)
cand["type_jump"] = [base(t, y) for t, y in zip(cand.product_type, cand.yr)]
cand = cand[cand.type_jump.notna()]  # only years with a peer baseline
cand["excess"] = cand.jump - cand.type_jump
cases = cand.sort_values("excess", ascending=False).drop_duplicates("unit_id").head(12)


def theme_shift(uid, y):
    cols = ", ".join(f"avg({k}::INT) FILTER (WHERE yr = {y}) - avg({k}::INT) FILTER (WHERE yr = {y - 1}) AS {k}" for k in SHOWN)
    s = con.execute(f"SELECT {cols} FROM rv WHERE unit_id = ? AND channel = 'new' AND low = 1", [uid]).df().iloc[0]
    s = s.drop("warranty_service").astype(float).sort_values(ascending=False)
    return [dict(theme=k, change=round(float(v), 3)) for k, v in s.head(3).items() if v > 0.02]


cases["rising_themes"] = [theme_shift(u, y) for u, y in zip(cases.unit_id, cases.yr)]
cases.to_parquet(C / "pq_cases.parquet", index=False)
log("\n## 6. Case studies: largest rise in low-star share vs the previous year, beyond the type's own change")
for _, r in cases.iterrows():
    log(f"- {r.unit_label} ({r.product_type}) {int(r.prev_yr)} -> {int(r.yr)}: {r.prev_low:.0%} -> {r.low_share:.0%} "
        f"(n {int(r.prev_n)} -> {int(r.n)}; peers moved {r.type_jump:+.0%}); rising: "
        + ", ".join(f"{LABELS[x['theme']]} {x['change']:+.0%}" for x in r.rising_themes))

con.execute(f"""COPY (SELECT product_type, brand, count(*) AS reviews FROM rv WHERE brand_set = 'Peers' GROUP BY 1, 2
               HAVING count(*) >= 200) TO '{C / "pq_peer_brands.parquet"}' (FORMAT parquet)""")
# Theme definitions for downstream readers (the assistant has no access to pipeline/): label, group, measured precision.
prec_path = ROOT / "eval/theme_precision.csv"
prec = pd.read_csv(prec_path).set_index("theme") if prec_path.exists() else pd.DataFrame(columns=["precision", "lo", "hi", "n"])
pd.DataFrame([dict(theme=k, label=LABELS[k], grp=next(g for g, ks in GROUPS.items() if k in ks),
                   precision=prec.precision.get(k), precision_lo=prec.lo.get(k), precision_hi=prec.hi.get(k),
                   weak=k in WEAK_THEMES) for k in THEMES]).to_parquet(C / "pq_theme_meta.parquet", index=False)
(C / "postpurchase_report.md").write_text("\n".join(out_lines) + "\n")

"""Comparator brands (Bissell, Dyson, iRobot, Keurig, Instant Pot): clean listings and reviews with the same rules as
the SharkNinja set, so ratings and complaint themes can be compared within a product type.

Comparators stay at listing level (parent_asin): there is no entity resolution across their listings, which is fine
for the uses here (life-cycle curves and theme shares by type). Only units in product types SharkNinja also sells are
kept; accessories, bundles, unclassified and renewed-titled listings are dropped. Launch = earliest of the listed
"Date First Available" and the first review, as for SharkNinja.

In:  data/raw/amazon2023/meta_comparators.jsonl, reviews_comparators.jsonl (scripts/extract_comparators.py)
Out: data/clean/cmp_listing.parquet, data/clean/cmp_review.parquet
Run: .venv/bin/python pipeline/comparators.py"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules as R  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/amazon2023"
C = ROOT / "data/clean"

# Peer listings that the title rules place in a SharkNinja type but that are a different kind of product (found by
# reading the most-reviewed peer listings per type, 2026-09-23): carpet shampooers and spot cleaners, wet-dry floor
# cleaners, handheld steam cleaners, non-steam powered mops, robot mops, air-fryer lids and boards, steamer baskets,
# accessory bundles. Peer "iron/steamer" listings are steam cleaners, steamer baskets and fans coloured "Iron", so that
# type is dropped for peers. Peer sweepers are mostly manual push sweepers (SharkNinja's are cordless), so that type is
# dropped too.
CMP_EXCLUDE = re.compile(r"(?i)carpet (cleaner|shampooer|steamer)|shampooer|deep cleaner|spot ?lifter|spot cleaner|"
                         r"crosswave|wet[- ]dry|spinwave|steamshot|hard surface steam cleaner|robot mop|braava|"
                         r"air fryer lid|cutting board|steamer basket|steamer insert|accessory bundle|accessor(y|ies)")
CMP_DROP_TYPES = {"iron/steamer", "sweeper"}
sn_types = set(pd.read_parquet(C / "sn_product_summary.parquet").query("~is_accessory").product_type.dropna())
skip = {"accessory/part", "bundle", "unclassified"}

rows = []
for line in (RAW / "meta_comparators.jsonl").open():
    d = json.loads(line)
    title = R.clean_str(d.get("title"))
    ptype, _ = R.product_type(d.get("categories"), title)
    det = d.get("details") or {}
    dfa = R.clean_str(det.get("Date First Available"))
    try:
        dfa = datetime.strptime(dfa, "%B %d, %Y").date() if dfa else None
    except ValueError:
        dfa = None
    keep = (ptype in sn_types and ptype not in skip | CMP_DROP_TYPES and not R.RENEWED_RE.search(title or "")
            and not CMP_EXCLUDE.search(title or ""))
    rows.append(dict(parent_asin=d["parent_asin"], brand=d["comparator_brand"], title=title, product_type=ptype,
                     kept=keep, date_first_available=dfa, average_rating=d.get("average_rating"),
                     rating_count=d.get("rating_number")))
L = pd.DataFrame(rows)

con = duckdb.connect()
con.register("listing", L[L.kept])
con.execute(f"""
CREATE TABLE rev AS
SELECT *, row_number() OVER (PARTITION BY user_id, parent_asin, "timestamp", md5(coalesce(text,''))
                             ORDER BY helpful_vote DESC) AS dup_rank
FROM read_json_auto('{RAW / "reviews_comparators.jsonl"}')
WHERE parent_asin IN (SELECT parent_asin FROM listing)
""")
con.execute("""
CREATE TABLE rev_clean AS
SELECT md5(user_id || parent_asin || "timestamp"::VARCHAR) AS review_id, r.parent_asin, l.brand, l.product_type,
       CAST(to_timestamp(r."timestamp" / 1000) AS DATE) AS review_date,
       date_trunc('month', to_timestamp(r."timestamp" / 1000))::DATE AS review_month,
       CAST(r.rating AS TINYINT) AS rating, r.verified_purchase, r.helpful_vote,
       nullif(trim(r.title), '') AS review_title, nullif(trim(r.text), '') AS review_text
FROM rev r JOIN listing l USING (parent_asin)
WHERE r.dup_rank = 1
""")
first = con.execute("SELECT parent_asin, min(review_date) AS first_review, count(*) AS n_reviews FROM rev_clean GROUP BY 1").df()
L = L.merge(first, on="parent_asin", how="left")
dfa, fr = pd.to_datetime(L.date_first_available), pd.to_datetime(L.first_review)
L["launch_date"] = pd.concat([dfa, fr], axis=1).min(axis=1).dt.date
L["launch_source"] = np.where(dfa.notna() & (fr.isna() | (dfa <= fr)), "listed date",
                              np.where(fr.notna(), "first review (proxy)", None))
L.to_parquet(C / "cmp_listing.parquet", index=False)
con.execute(f"COPY rev_clean TO '{C / 'cmp_review.parquet'}' (FORMAT parquet)")

k = L[L.kept]
print(f"listings {len(L):,}; kept units {len(k):,}; reviews {con.execute('SELECT count(*) FROM rev_clean').fetchone()[0]:,}")
print(k.groupby(["product_type", "brand"]).agg(listings=("parent_asin", "count"), reviews=("n_reviews", "sum"))
      .query("reviews > 0").to_string())

"""Export the analysis tables to static JSON for the front end (web/data/). Deterministic; no model involved.
  web/data/portfolio.json        totals, monthly series, families, pooled findings, method numbers
  web/data/products.json         one row per product (for the picker)
  web/data/p/<file>.json         one file per product: monthly series, events with comparison bands, listings
Run: .venv/bin/python pipeline/export_web.py"""
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
OUT = ROOT / "web/data"
COMPLETE_THROUGH = "2023-03"


def clean(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else round(float(v), 3)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return v


def rec(d):
    return {k: clean(v) for k, v in d.items()}


def file_of(pid):
    return re.sub(r"[^A-Za-z0-9_-]", "_", pid) + ".json"


if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "p").mkdir(parents=True)

S = pd.read_parquet(C / "sn_product_summary.parquet")
P = pd.read_parquet(C / "sn_panel_month.parquet")
T = pd.read_parquet(C / "sn_event_test.parquet")
B = pd.read_parquet(C / "sn_event_band.parquet")
PO = pd.read_parquet(C / "sn_event_pooled.parquet")
LP = pd.read_parquet(C / "sn_listing_product.parquet")
P["m"] = pd.to_datetime(P["month"]).dt.strftime("%Y-%m")

# ---------------- products index ----------------
ev_counts = T.groupby("product_id").agg(n_events=("event_id", "count"),
                                         n_tested=("verdict", lambda v: int((v != "not_enough_data").sum())))
S2 = S.merge(ev_counts, left_on="product_id", right_index=True, how="left")
products = []
for r in S2.itertuples():
    if r.maker == "unrelated":
        continue
    products.append(rec(dict(id=r.product_id, file=file_of(r.product_id), title=r.canonical_title, brand=r.brand,
                             type=r.product_type, family=r.family, model=r.model_key, accessory=bool(r.is_accessory),
                             self_empty=bool(r.self_empty_variant), bundle=r.product_id.startswith("SN-B-"),
                             launch=r.launch_date, launch_source=r.launch_source, listings=r.n_listings,
                             brand_store=r.n_brand_store, renewed=r.n_renewed,
                             reviews_new=0 if pd.isna(r.reviews_new) else r.reviews_new,
                             reviews_renewed=0 if pd.isna(r.reviews_renewed) else r.reviews_renewed,
                             rating_new=r.avg_rating_new, events=0 if pd.isna(r.n_events) else r.n_events,
                             tested=0 if pd.isna(r.n_tested) else r.n_tested)))
(OUT / "products.json").write_text(json.dumps(products, separators=(",", ":")))

# ---------------- per product ----------------
Pp = P.pivot_table(index=["product_id", "m"], columns="channel", values=["reviews", "avg_rating"], aggfunc="first")
Pp.columns = [f"{a}_{b}" for a, b in Pp.columns]
Pp = Pp.reset_index()
bands = {eid: g.sort_values("rel_month") for eid, g in B.groupby("event_id")}
for pid, g in Pp.groupby("product_id"):
    months = [dict(m=r.m, new=int(r.reviews_new) if pd.notna(getattr(r, "reviews_new", np.nan)) else 0,
                   renewed=int(r.reviews_renewed) if "reviews_renewed" in g and pd.notna(r.reviews_renewed) else 0,
                   rating_new=clean(getattr(r, "avg_rating_new", None)),
                   rating_renewed=clean(getattr(r, "avg_rating_renewed", None)))
              for r in g.sort_values("m").itertuples()]
    evs = []
    for e in T[T.product_id == pid].sort_values("event_month").itertuples():
        d = rec(dict(id=e.event_id, type=e.event_type, month=e.event_month, detail=e.detail, related=e.related_product,
                     window=e.window, verdict=e.verdict, reason=e.reason, pre_mean=getattr(e, "pre_mean", None),
                     post_mean=getattr(e, "post_mean", None), effect_pct=getattr(e, "effect_pct", None),
                     lo_pct=getattr(e, "lo_pct", None), hi_pct=getattr(e, "hi_pct", None),
                     n_controls=getattr(e, "n_controls", None), control_tier=getattr(e, "control_tier", None),
                     p_value=getattr(e, "p_value", None), near_zero_after=getattr(e, "near_zero_after", None)))
        if e.event_id in bands:
            d["band"] = [rec(dict(r=b.rel_month, m=b.month, v=b.product_value, lo=b.band_lo, mid=b.band_mid, hi=b.band_hi))
                         for b in bands[e.event_id].itertuples()]
        evs.append(d)
    lst = [rec(dict(asin=r.parent_asin, title=r.title, segment=r.segment, method=r.link_method, rating=r.average_rating,
                    ratings=r.rating_count)) for r in LP[LP.product_id == pid].itertuples()]
    s = S[S.product_id == pid].iloc[0]
    body = dict(id=pid, title=s.canonical_title, brand=s.brand, type=s.product_type, family=s.family, model=s.model_key,
                launch=clean(s.launch_date), launch_source=s.launch_source, months=months, events=evs, listings=lst)
    (OUT / "p" / file_of(pid)).write_text(json.dumps(body, separators=(",", ":")))

# ---------------- portfolio ----------------
tot = P.groupby(["m", "channel"]).reviews.sum().unstack(fill_value=0).reset_index()
fam = (S[S.family.notna() & ~S.is_accessory].groupby("family")
       .agg(type=("product_type", lambda x: x.value_counts().index[0]), products=("product_id", "count"),
            reviews_new=("reviews_new", "sum"), reviews_renewed=("reviews_renewed", "sum")).reset_index()
       .sort_values("reviews_new", ascending=False))
portfolio = dict(
    complete_through=COMPLETE_THROUGH,
    months=[dict(m=r.m, new=int(r.new), renewed=int(r.renewed)) for r in tot.itertuples()],
    families=[rec(r._asdict()) for r in fam.itertuples(index=False)],
    pooled=[rec(r._asdict()) for r in PO.itertuples(index=False)],
    stats=dict(listings_in_scope=int((LP.link_method != "excluded_unrelated").sum()), products=len(products),
               reviews=int(P.reviews.sum()), reviews_new=int(P[P.channel == "new"].reviews.sum()),
               reviews_renewed=int(P[P.channel == "renewed"].reviews.sum()), events=len(T),
               events_tested=int((T.verdict != "not_enough_data").sum()),
               verdicts={k: int(v) for k, v in T.verdict.value_counts().items()}),
    matcher=dict(benchmark_f1=0.852, sn_precision=0.869, sn_recall=0.914, sn_precision_adjudicated=0.948,
                 sn_recall_adjudicated=0.917),
)
(OUT / "portfolio.json").write_text(json.dumps(portfolio, separators=(",", ":")))
size = sum(f.stat().st_size for f in OUT.rglob("*.json"))
print(f"products {len(products):,}; product files {len(list((OUT / 'p').glob('*.json'))):,}; total {size / 1e6:.1f} MB")

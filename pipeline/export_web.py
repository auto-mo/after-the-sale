"""Export the post-purchase analysis to static JSON for the front end (web/data/). Deterministic; no model involved.
  web/data/portfolio.json   stats, theme definitions with measured precision, findings, type table, families, cases
  web/data/products.json    one row per product (for the picker and tables)
  web/data/p/<file>.json    one file per product: monthly series, complaint mix with quotes, life cycle, years, refurbished
Run: .venv/bin/python pipeline/export_web.py  (after lifecycle.py)"""
import json
import re
import shutil
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from themes import GROUPS, LABELS, THEMES, WEAK_THEMES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
E = ROOT / "eval"
OUT = ROOT / "web/data"
COMPLETE_THROUGH = "2023-03"
MIN_LOW = 30          # low-star reviews needed before a product's complaint mix is shown
PROBLEM = [k for k in THEMES if k not in WEAK_THEMES and k != "warranty_service"]
SHOWN = PROBLEM + [k for k in ["warranty_service"] if k not in WEAK_THEMES]


def clean(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    if isinstance(v, (list, tuple, np.ndarray)):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v


def rec(d):
    return {k: clean(v) for k, v in d.items()}


def recs(df):
    return [rec(r) for r in df.to_dict("records")]


def file_of(pid):
    return re.sub(r"[^A-Za-z0-9_-]", "_", pid) + ".json"


def shares(row, keys=SHOWN):
    return {k: clean(row[k]) for k in keys}


if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "p").mkdir(parents=True)
con = duckdb.connect()
S = pd.read_parquet(C / "sn_product_summary.parquet")
P = pd.read_parquet(C / "sn_panel_month.parquet")
LP = pd.read_parquet(C / "sn_listing_product.parquet")
P["m"] = pd.to_datetime(P["month"]).dt.strftime("%Y-%m")
con.execute(f"CREATE VIEW rv AS SELECT * FROM '{C / 'pq_review.parquet'}'")
prec = pd.read_csv(E / "theme_precision.csv").set_index("theme") if (E / "theme_precision.csv").exists() else None
group_of = {k: g for g, ks in GROUPS.items() for k in ks}

# ---------------- per-product aggregates ----------------
agg_cols = ", ".join(f"avg({k}::INT) FILTER (WHERE low = 1) AS {k}" for k in SHOWN)
U = con.execute(f"""
SELECT unit_id AS product_id, count(*) FILTER (WHERE channel = 'new') AS n_new,
       count(*) FILTER (WHERE low = 1) AS n_low, avg(low) FILTER (WHERE channel = 'new') AS low_share_new,
       {agg_cols}
FROM rv WHERE brand_set = 'SharkNinja' AND channel = 'new' GROUP BY 1
""").df().set_index("product_id")
top_theme = {}
for pid, r in U.iterrows():
    if r.n_low >= MIN_LOW:
        s = r[PROBLEM].astype(float)
        top_theme[pid] = s.idxmax() if s.max() > 0 else None
drift = pd.read_parquet(C / "pq_drift.parquet")
dsn = drift[drift.brand_set == "SharkNinja"].set_index("unit_id")

# ---------------- products index ----------------
products = []
for r in S.itertuples():
    if r.maker == "unrelated":
        continue
    u = U.loc[r.product_id] if r.product_id in U.index else None
    products.append(rec(dict(
        id=r.product_id, file=file_of(r.product_id), title=r.canonical_title, brand=r.brand, type=r.product_type,
        family=r.family, model=r.model_key, accessory=bool(r.is_accessory), self_empty=bool(r.self_empty_variant),
        bundle=r.product_id.startswith("SN-B-"), launch=r.launch_date, launch_source=r.launch_source,
        listings=r.n_listings, brand_store=r.n_brand_store, renewed=r.n_renewed,
        reviews_new=0 if pd.isna(r.reviews_new) else r.reviews_new,
        reviews_renewed=0 if pd.isna(r.reviews_renewed) else r.reviews_renewed, rating_new=r.avg_rating_new,
        low_share=None if u is None else u.low_share_new, low_reviews=0 if u is None else u.n_low,
        top_theme=top_theme.get(r.product_id),
        drift=dsn.change.get(r.product_id) if r.product_id in dsn.index else None)))
(OUT / "products.json").write_text(json.dumps(products, separators=(",", ":"), allow_nan=False))

# ---------------- quotes: for each product and theme, the most helpful short excerpts ----------------
rev = con.execute(f"""
SELECT r.review_id, r.review_date, r.rating, r.verified_purchase, r.helpful_vote, r.review_title, r.review_text,
       v.unit_id AS product_id, v.channel, {", ".join(f"v.{k}" for k in SHOWN)}
FROM '{C / "sn_review.parquet"}' r JOIN rv v USING (review_id)
WHERE v.brand_set = 'SharkNinja' AND v.low = 1
""").df()
rev["text"] = rev.review_text.fillna("")
COMPILED = {k: re.compile(THEMES[k], re.I) for k in SHOWN}


def excerpt(text, k, width=260):
    t = re.sub(r"\s+", " ", text).strip()
    m = COMPILED[k].search(t.lower())
    if not m or len(t) <= width:
        return t[:width] + ("…" if len(t) > width else "")
    a = max(0, m.start() - width // 2)
    b = min(len(t), a + width)
    a = max(0, b - width)
    return ("…" if a > 0 else "") + t[a:b].strip() + ("…" if b < len(t) else "")


def quotes_for(g, k, n=2):
    h = g[g[k]].sort_values(["verified_purchase", "helpful_vote", "review_date"], ascending=[False, False, False])
    out = []
    for r in h.head(n).itertuples():
        out.append(rec(dict(date=r.review_date, rating=r.rating, verified=r.verified_purchase, helpful=r.helpful_vote,
                            title=r.review_title, text=excerpt(r.text, k))))
    return out


# ---------------- type references (SharkNinja type average and peers) ----------------
TT = pd.read_parquet(C / "pq_theme_type.parquet")
type_ref = {(r.brand_set, r.product_type): r for r in TT.itertuples()}
CURVE = pd.read_parquet(C / "pq_curve.parquet")
REF_CELLS = pd.read_parquet(C / "pq_refurb_cells.parquet")
# Peer brands per type, only those with 200+ reviews of it (pipeline/lifecycle.py writes the same table for the assistant)
peer_brands = (pd.read_parquet(C / "pq_peer_brands.parquet").sort_values("brand").groupby("product_type").brand
               .apply(list).to_dict())

# ---------------- per product ----------------
Pp = P.pivot_table(index=["product_id", "m"], columns="channel", values=["reviews", "avg_rating", "low_ratings"],
                   aggfunc="first")
Pp.columns = [f"{a}_{b}" for a, b in Pp.columns]
Pp = Pp.reset_index()
life = con.execute("""SELECT unit_id AS product_id, age_band, min(age_m) AS age_from, count(*) AS n, avg(rating) AS rating,
                             avg(low) AS low_share FROM rv WHERE brand_set = 'SharkNinja' AND channel = 'new' GROUP BY 1, 2""").df()
years = con.execute(f"""SELECT unit_id AS product_id, yr, count(*) AS n, avg(rating) AS rating, avg(low) AS low_share,
                               count(*) FILTER (WHERE low = 1) AS n_low, {agg_cols}
                        FROM rv WHERE brand_set = 'SharkNinja' AND channel = 'new' GROUP BY 1, 2""").df()
chan = con.execute(f"""SELECT unit_id AS product_id, channel, count(*) AS n, avg(rating) AS rating, avg(low) AS low_share,
                              count(*) FILTER (WHERE low = 1) AS n_low, {agg_cols}
                       FROM rv WHERE brand_set = 'SharkNinja' GROUP BY 1, 2""").df()
life_g, years_g, chan_g = (dict(tuple(d.groupby("product_id"))) for d in (life, years, chan))
rev_g = dict(tuple(rev[rev.channel == "new"].groupby("product_id")))
rev_ref_g = dict(tuple(rev[rev.channel == "refurbished"].groupby("product_id")))
band_order = {b: i for i, b in enumerate(["0 to 6 months", "7 to 12 months", "Year 2", "Years 3 to 4", "Year 5+"])}

for pid, g in Pp.groupby("product_id"):
    s = S[S.product_id == pid].iloc[0]
    months = [dict(m=r.m, new=int(r.reviews_new) if "reviews_new" in g and pd.notna(r.reviews_new) else 0,
                   renewed=int(r.reviews_renewed) if "reviews_renewed" in g and pd.notna(r.reviews_renewed) else 0,
                   low_new=int(r.low_ratings_new) if "low_ratings_new" in g and pd.notna(r.low_ratings_new) else 0,
                   rating_new=clean(getattr(r, "avg_rating_new", None)),
                   rating_renewed=clean(getattr(r, "avg_rating_renewed", None)))
              for r in g.sort_values("m").itertuples()]
    body = dict(**rec(dict(id=pid, title=s.canonical_title, brand=s.brand, type=s.product_type, family=s.family,
                           model=s.model_key, launch=s.launch_date, launch_source=s.launch_source)), months=months,
                listings=[rec(dict(asin=r.parent_asin, title=r.title, segment=r.segment, method=r.link_method,
                                   rating=r.average_rating, ratings=r.rating_count))
                          for r in LP[LP.product_id == pid].itertuples()])
    if pid in U.index:
        u = U.loc[pid]
        th = dict(n_low=int(u.n_low), shown=bool(u.n_low >= MIN_LOW), shares=shares(u))
        if th["shown"]:
            ranked = sorted(PROBLEM, key=lambda k: -(u[k] or 0))
            th["top"] = [dict(theme=k, share=clean(u[k]), quotes=quotes_for(rev_g.get(pid, rev.iloc[:0]), k))
                         for k in ranked[:4] if (u[k] or 0) > 0]
        sn_ref = type_ref.get(("SharkNinja", s.product_type))
        pe_ref = type_ref.get(("Peers", s.product_type))
        th["type_sharkninja"] = dict(n_low=int(sn_ref.n_low), shares=shares(sn_ref._asdict())) if sn_ref else None
        th["type_peers"] = dict(n_low=int(pe_ref.n_low), brands=list(peer_brands.get(s.product_type, [])),
                                shares=shares(pe_ref._asdict())) if pe_ref else None
        body["themes"] = th
        lg = life_g.get(pid)
        body["lifecycle"] = sorted(recs(lg.drop(columns="product_id")), key=lambda x: band_order[x["age_band"]]) if lg is not None else []
        cref = CURVE[(CURVE.product_type == s.product_type)]
        body["lifecycle_ref"] = recs(cref[["brand_set", "age_band", "band_order", "units", "rating", "low_share"]])
        body["drift"] = rec(dsn.loc[pid][["n1", "r1", "l1", "n3", "r3", "l3", "change"]].to_dict()) if pid in dsn.index else None
        yg = years_g.get(pid)
        yl = []
        if yg is not None:
            for r in yg.sort_values("yr").itertuples():
                d = dict(yr=r.yr, n=r.n, rating=r.rating, low_share=r.low_share, n_low=r.n_low, top_theme=None)
                if r.n_low >= 15:
                    ss = pd.Series({k: getattr(r, k) for k in PROBLEM}).astype(float)
                    d["top_theme"] = ss.idxmax() if ss.max() > 0 else None
                    d["top_share"] = ss.max()
                yl.append(rec(d))
        body["years"] = yl
        cg = chan_g.get(pid)
        if cg is not None and set(cg.channel) == {"new", "refurbished"}:
            cc = REF_CELLS[REF_CELLS.unit_id == pid]
            ch = {r.channel: dict(n=int(r.n), rating=clean(r.rating), low_share=clean(r.low_share), n_low=int(r.n_low),
                                  shares=shares(r._asdict())) for r in cg.itertuples()}
            body["refurb"] = dict(channels=ch, cells=recs(cc[["yr", "r_ref", "n_ref", "r_new", "n_new", "gap"]]),
                                  quotes=[q for k in ["missing_parts", "arrived_damaged_used", "not_as_described", "dead_on_arrival"]
                                          for q in quotes_for(rev_ref_g.get(pid, rev.iloc[:0]), k, 1)][:3])
    (OUT / "p" / file_of(pid)).write_text(json.dumps(body, separators=(",", ":"), allow_nan=False))

# ---------------- portfolio / findings ----------------
FS = pd.read_parquet(C / "pq_fail_summary.parquet")
FB = pd.read_parquet(C / "pq_fail_band.parquet")
TR = pd.read_parquet(C / "pq_trend.parquet")
TRT = pd.read_parquet(C / "pq_trend_type.parquet")
RT = pd.read_parquet(C / "pq_refurb_themes.parquet").set_index("channel")
EV = pd.read_parquet(C / "sn_event_test.parquet")
_pb = re.search(r"held-out placebo B:.*?\(([\d.]+)% of those tested\)", (C / "events_report.md").read_text())
PLACEBO_B = round(float(_pb.group(1)) / 100, 3) if _pb else None
CASES = pd.read_parquet(C / "pq_cases.parquet")
types = sorted(set(TT[TT.brand_set == "Peers"].product_type) & set(TT[TT.brand_set == "SharkNinja"].product_type)
               & set(TRT.product_type))


def drift_summary(g):
    return dict(products=len(g), mean=clean(g.change.mean()), median=clean(g.change.median()),
                fell=int((g.change < 0).sum()), low_year1=clean(g.l1.mean()), low_years3to4=clean(g.l3.mean()))


type_rows = []
for t in types:
    sn, pe = type_ref[("SharkNinja", t)], type_ref[("Peers", t)]
    d_sn, d_pe = drift[(drift.product_type == t) & (drift.brand_set == "SharkNinja")], drift[(drift.product_type == t) & (drift.brand_set == "Peers")]
    f = FS[FS.product_type == t].set_index("brand_set")
    gaps = sorted(PROBLEM, key=lambda k: -((getattr(sn, k) or 0) - (getattr(pe, k) or 0)))
    lows = con.execute("SELECT brand_set, avg(low) FROM rv WHERE channel='new' AND product_type=? GROUP BY 1", [t]).fetchall()
    type_rows.append(rec(dict(
        type=t, peer_brands=list(peer_brands.get(t, [])), n_low_sn=sn.n_low, n_low_peers=pe.n_low,
        low_share=dict(lows), shares_sn=shares(sn._asdict()), shares_peers=shares(pe._asdict()),
        biggest_gap=[dict(theme=k, sn=clean(getattr(sn, k)), peers=clean(getattr(pe, k))) for k in gaps[:3]],
        drift_sn=clean(d_sn.change.mean()) if len(d_sn) else None, drift_sn_n=len(d_sn),
        drift_peers=clean(d_pe.change.mean()) if len(d_pe) else None, drift_peers_n=len(d_pe),
        fail_median_sn=clean(f.median_months.get("SharkNinja")), fail_n_sn=clean(f.n.get("SharkNinja")),
        fail_median_peers=clean(f.median_months.get("Peers")), fail_n_peers=clean(f.n.get("Peers")))))

fam = (S[S.family.notna() & ~S.is_accessory].groupby("family")
       .agg(type=("product_type", lambda x: x.value_counts().index[0]), products=("product_id", "count"),
            reviews_new=("reviews_new", "sum"), reviews_renewed=("reviews_renewed", "sum")).reset_index())
fl = con.execute("""SELECT s.family, avg(v.low) AS low_share, count(*) FILTER (WHERE v.low = 1) AS n_low
                    FROM rv v JOIN 'data/clean/sn_product_summary.parquet' s ON s.product_id = v.unit_id
                    WHERE v.brand_set = 'SharkNinja' AND v.channel = 'new' GROUP BY 1""".replace("data/clean", str(C))).df()
ft = con.execute(f"""SELECT s.family, {agg_cols.replace('low = 1', 'v.low = 1')}
                     FROM rv v JOIN '{C / "sn_product_summary.parquet"}' s ON s.product_id = v.unit_id
                     WHERE v.brand_set = 'SharkNinja' AND v.channel = 'new' GROUP BY 1""").df().set_index("family")
fam = fam.merge(fl, on="family", how="left")
fam["top_theme"] = [(ft.loc[f, PROBLEM].astype(float).idxmax() if f in ft.index and n >= MIN_LOW else None)
                    for f, n in zip(fam.family, fam.n_low.fillna(0))]
fam = fam.sort_values("reviews_new", ascending=False)

arrival = ["missing_parts", "arrived_damaged_used", "not_as_described", "dead_on_arrival", "stopped_working"]
cells = REF_CELLS
naive = con.execute("""SELECT avg(rating) FILTER (WHERE channel='refurbished'), avg(rating) FILTER (WHERE channel='new')
                       FROM rv WHERE brand_set = 'SharkNinja'""").fetchone()
nstats = con.execute("""SELECT brand_set, channel, count(*), count(DISTINCT unit_id) FROM rv GROUP BY 1, 2""").fetchall()
theme_meta = []
for k in SHOWN:
    m = dict(key=k, label=LABELS[k], group=group_of[k])
    if prec is not None and k in prec.index:
        m.update(precision=clean(prec.loc[k, "precision"]), precision_lo=clean(prec.loc[k, "lo"]),
                 precision_hi=clean(prec.loc[k, "hi"]), precision_n=int(prec.loc[k, "n"]))
    theme_meta.append(m)

portfolio = dict(
    complete_through=COMPLETE_THROUGH,
    stats=dict(listings_in_scope=int((LP.link_method != "excluded_unrelated").sum()),
               listings_bundles=int((LP.link_method == "bundle").sum()), products=len(products),
               reviews={f"{a}|{b}": dict(reviews=int(c), units=int(d)) for a, b, c, d in nstats},
               peer_brands=["Bissell", "Dyson", "iRobot", "Keurig", "Instant Pot"]),
    themes=theme_meta, weak_themes=sorted(WEAK_THEMES),
    findings=dict(
        drift=dict(sharkninja=drift_summary(drift[drift.brand_set == "SharkNinja"]),
                   peers=drift_summary(drift[drift.brand_set == "Peers"]), min_reviews=100),
        curve=recs(CURVE[CURVE.product_type == "All types"][["brand_set", "age_band", "band_order", "units", "rating", "low_share"]]),
        trend=recs(TR[["brand_set", "yr", "low_share", "rating", "types"]]),
        fail=dict(summary=recs(FS), bands=recs(FB)),
        refurb=dict(naive_refurb=clean(naive[0]), naive_new=clean(naive[1]), cells=len(cells),
                    products=int(cells.unit_id.nunique()), mean_gap=clean(cells.gap.mean()),
                    median_gap=clean(cells.gap.median()), lower_share=clean((cells.gap < 0).mean()),
                    n_low_refurb=int(RT.loc["refurbished", "n_low"]), n_low_new=int(RT.loc["new", "n_low"]),
                    arrival={k: dict(refurbished=clean(RT.loc["refurbished", k]), new=clean(RT.loc["new", k])) for k in arrival}),
        cases=[rec(dict(product_id=r.unit_id, file=file_of(r.unit_id), label=r.unit_label, type=r.product_type,
                        year=r.yr, prev_year=r.prev_yr, n=r.n, prev_n=r.prev_n, low_share=r.low_share,
                        prev_low_share=r.prev_low, peers_change=r.type_jump, excess=r.excess,
                        rising=list(r.rising_themes))) for r in CASES.itertuples()],
    ),
    types=type_rows,
    families=recs(fam),
    matcher=dict(benchmark_f1=0.852, sn_precision=0.869, sn_recall=0.914, sn_precision_adjudicated=0.948,
                 sn_recall_adjudicated=0.917),
    event_appendix=dict(events=int(len(EV)), testable=int((EV.verdict != "not_enough_data").sum()),
                        survive_fdr=int(EV.survives_fdr.fillna(False).sum()), placebo_false_alarm=PLACEBO_B),
    default_product="SN-S3501" if (S.product_id == "SN-S3501").any() else "SN-HV322",
)
(OUT / "portfolio.json").write_text(json.dumps(portfolio, separators=(",", ":"), allow_nan=False))
size = sum(f.stat().st_size for f in OUT.rglob("*.json"))
print(f"products {len(products):,}; product files {len(list((OUT / 'p').glob('*.json'))):,}; total {size / 1e6:.1f} MB")

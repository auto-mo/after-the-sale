"""Phase 3: raw -> data/clean/*.parquet. Raw files are read-only. Every rule's coverage goes to
data/clean/cleaning_report.md. Run: .venv/bin/python pipeline/clean.py"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules as R  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)
report = []


def log(section, lines):
    report.append(f"\n## {section}\n" + "\n".join(f"- {l}" for l in lines))
    print(f"[{section}]", *lines, sep="\n  ")


def pct(a, b):
    return f"{a:,} / {b:,} ({100 * a / b:.1f}%)" if b else "0"


# =============== SharkNinja listings ===============
meta = [json.loads(l) for l in open(RAW / "amazon2023" / "meta_sharkninja.jsonl")]
rows = []
for d in meta:
    det = d.get("details") or {}
    title = R.clean_str(d.get("title"))
    ptype, ptype_src = R.product_type(d.get("categories"), title)
    is_acc = ptype == "accessory/part"
    model, msrc, mconf, compat, part, cands = R.extract_model(det.get("Item model number"), title, is_acc)
    cap, cap_src = R.capacity_qt(det.get("Capacity"), title)
    watt, watt_src = R.wattage_w(det.get("Wattage"), title)
    dfa = R.clean_str(det.get("Date First Available"))
    try:
        dfa = datetime.strptime(dfa, "%B %d, %Y").date() if dfa else None
    except ValueError:
        dfa = None
    store = d.get("store")
    brand_detail = R.clean_str(det.get("Brand"))
    brand = "Shark" if re.search(r"(?i)\bshark", title or "") else "Ninja" if re.search(r"(?i)\bninja", title or "") else store
    if store in ("Shark", "Ninja"):
        brand = store
    rows.append(dict(
        parent_asin=d["parent_asin"], title=title, store=store,
        segment="renewed" if store == "Amazon Renewed" else "brand_store",
        renewed_in_title=bool(R.RENEWED_RE.search(title or "")),
        brand=brand, maker=R.maker(title, is_acc, store),
        refurbisher=brand_detail if store == "Amazon Renewed" and brand_detail and not re.search(r"(?i)shark|ninja", brand_detail) else None,
        product_type=ptype, product_type_source=ptype_src,
        model_no=model, model_source=msrc, model_confidence=mconf,
        model_candidates=cands, compatible_models=compat, part_no=part,
        capacity_qt=cap, capacity_source=cap_src, wattage_w=watt, wattage_source=watt_src,
        price=R.parse_price(d.get("price")),
        average_rating=d.get("average_rating"), rating_count=d.get("rating_number"),
        date_first_available=dfa,
        main_category=R.clean_str(d.get("main_category")),
        category_path=" > ".join(d.get("categories") or []) or None,
        best_sellers_rank=json.dumps(det.get("Best Sellers Rank")) if det.get("Best Sellers Rank") else None,
    ))
L = pd.DataFrame(rows)

# base_model: AMZ always stripped; other suffixes only when a sibling model shares the stripped base.
L["model_amz"] = L["model_no"].map(lambda m: R.AMZ_RE.sub("", m) if isinstance(m, str) else None)
known = set(L["model_amz"].dropna())
stripped = L["model_amz"].map(lambda m: R.SUFFIX_RE.sub("", m) if isinstance(m, str) else None)
group_raw = defaultdict(set)
for raw, s in zip(L["model_amz"], stripped):
    if isinstance(raw, str):
        group_raw[s].add(raw)


def base_of(raw, s):
    if not isinstance(raw, str):
        return None, None
    if s != raw and len(s) >= 4 and (s in known or len(group_raw[s]) > 1):
        return s, "suffix_stripped_sibling"
    return raw, "as_is"


bb = [base_of(r, s) for r, s in zip(L["model_amz"], stripped)]
L["base_model"] = [b for b, _ in bb]
L["base_model_rule"] = [r for _, r in bb]
L.loc[L["model_no"].notna() & (L["model_no"] != L["model_amz"]) & (L["base_model_rule"] == "as_is"), "base_model_rule"] = "amz_stripped"
L = L.drop(columns=["model_amz"])
L["core_model"] = [R.core_model(b) if isinstance(b, str) and t != "accessory/part" else (b if isinstance(b, str) else None)
                   for b, t in zip(L["base_model"], L["product_type"])]
# Manual aliases (data/manual/model_aliases.csv): different digits, same unit, with recorded evidence.
ALIASES = dict(pd.read_csv(ROOT / "data/manual/model_aliases.csv")[["alias_core", "canonical_core"]].values)
L["core_alias_applied"] = L["core_model"].isin(ALIASES)
L["core_model"] = L["core_model"].map(lambda c: ALIASES.get(c, c) if isinstance(c, str) else c)
# Self-empty / auto-empty base versions are a separate purchase (price, weight) of the same core unit.
L["self_empty"] = [bool(isinstance(b, str) and re.search(r"AE$", b)) or bool(re.search(r"(?i)self[- ]empty|auto[- ]empty", t or ""))
                   for b, t in zip(L["base_model"], L["title"])]
L["dup_title_count"] = L.groupby("title")["parent_asin"].transform("count")

n = len(L)
bs = L[L.segment == "brand_store"]
rn = L[L.segment == "renewed"]
log("SharkNinja listings", [
    f"rows: {n:,} (brand store {len(bs):,}, renewed {len(rn):,}); none dropped",
    f"model_no found: {pct(L.model_no.notna().sum(), n)}; brand store {pct(bs.model_no.notna().sum(), len(bs))}; renewed {pct(rn.model_no.notna().sum(), len(rn))}",
    "model_source: " + ", ".join(f"{k} {v:,}" for k, v in L.model_source.value_counts().items()),
    f"title named a different model than the details field (title wins): {(L.model_source == 'title_explicit_over_details').sum():,}",
    f"manual alias applied: {L.core_alias_applied.sum():,} listings; self-empty variants: {L.self_empty.sum():,}; bundles: {(L.product_type == 'bundle').sum():,}",
    "model_confidence: " + ", ".join(f"{k} {v:,}" for k, v in L.model_confidence.value_counts().items()),
    f"accessories with compatible_models list: {pct((L.compatible_models.map(len) > 0).sum(), (L.product_type == 'accessory/part').sum())}",
    "base_model_rule: " + ", ".join(f"{k} {v:,}" for k, v in L.base_model_rule.value_counts(dropna=False).items()),
    f"distinct model_no {L.model_no.nunique():,} -> distinct base_model {L.base_model.nunique():,} -> distinct core_model {L.core_model.nunique():,}",
    "product_type: " + ", ".join(f"{k} {v:,}" for k, v in L.product_type.value_counts().items()),
    "product_type_source: " + ", ".join(f"{k} {v:,}" for k, v in L.product_type_source.value_counts().items()),
    f"capacity_qt: {pct(L.capacity_qt.notna().sum(), n)}; wattage_w: {pct(L.wattage_w.notna().sum(), n)}",
    f"price present: {pct(L.price.notna().sum(), n)} (brand store {pct(bs.price.notna().sum(), len(bs))})",
    f"date_first_available parsed: {pct(L.date_first_available.notna().sum(), n)}",
    f"renewed listings without renewed wording in title: {(~rn.renewed_in_title).sum():,}; brand-store listings with renewed wording: {bs.renewed_in_title.sum():,}",
    f"refurbisher named (not Shark/Ninja): {L.refurbisher.notna().sum():,} ({', '.join(f'{k} {v}' for k, v in L.refurbisher.value_counts().head(5).items())})",
    "maker: " + ", ".join(f"{k} {v:,}" for k, v in L.maker.value_counts().items()) + f" (brand store only: " + ", ".join(f"{k} {v:,}" for k, v in bs.maker.value_counts().items()) + ")",
    f"listings sharing an exact title with another listing: {(L.dup_title_count > 1).sum():,}",
])

# Link check: renewed -> brand store via base_model (the join the matcher must beat).
bs_bases = set(bs.core_model.dropna())
rn_linked = rn.core_model.isin(bs_bases).sum()
log("Key-join coverage before matching", [
    f"renewed listings whose core_model exists in brand store: {pct(rn_linked, len(rn))}",
    f"brand-store listings sharing a base_model with another brand-store listing: {pct(bs.base_model.dropna().duplicated(keep=False).sum(), len(bs))}",
])
L.to_parquet(CLEAN / "sn_listing.parquet", index=False)

# =============== SharkNinja reviews (SQL) ===============
con = duckdb.connect()
con.register("listing", L[["parent_asin", "date_first_available"]])
con.execute(f"""
CREATE TABLE rev AS
SELECT *, row_number() OVER (PARTITION BY user_id, parent_asin, "timestamp", md5(coalesce(text,''))
                             ORDER BY helpful_vote DESC) AS dup_rank
FROM read_json_auto('{RAW / "amazon2023" / "reviews_sharkninja.jsonl"}')
""")
con.execute("""
CREATE TABLE rev_clean AS
SELECT md5(user_id || parent_asin || "timestamp"::VARCHAR) AS review_id,
       r.parent_asin, r.asin, r.asin <> r.parent_asin AS is_variant_asin,
       to_timestamp(r."timestamp" / 1000) AS review_ts,
       CAST(to_timestamp(r."timestamp" / 1000) AS DATE) AS review_date,
       date_trunc('month', to_timestamp(r."timestamp" / 1000))::DATE AS review_month,
       CAST(r.rating AS TINYINT) AS rating, r.verified_purchase, r.helpful_vote, r.user_id,
       nullif(trim(r.title), '') AS review_title, nullif(trim(r.text), '') AS review_text,
       l.date_first_available IS NOT NULL
         AND CAST(to_timestamp(r."timestamp" / 1000) AS DATE) < l.date_first_available AS before_launch
FROM rev r LEFT JOIN listing l USING (parent_asin)
WHERE r.dup_rank = 1
""")
con.execute(f"COPY rev_clean TO '{CLEAN / 'sn_review.parquet'}' (FORMAT parquet)")
con.execute(f"""COPY (SELECT parent_asin, asin, user_id, "timestamp", rating, 'exact duplicate: same user, listing, timestamp and text' AS reason
                FROM rev WHERE dup_rank > 1) TO '{CLEAN / 'rejected_reviews.parquet'}' (FORMAT parquet)""")
q = lambda s: con.execute(s).fetchone()
tot, kept = q("SELECT count(*) FROM rev")[0], q("SELECT count(*) FROM rev_clean")[0]
bl = q("SELECT count(*), count(DISTINCT parent_asin) FROM rev_clean WHERE before_launch")
dmin, dmax = q("SELECT min(review_date), max(review_date) FROM rev_clean")
log("SharkNinja reviews", [
    f"raw {tot:,}; kept {kept:,}; rejected exact duplicates {tot - kept:,} -> rejected_reviews.parquet",
    f"orphan reviews (no listing): {q('SELECT count(*) FROM rev_clean WHERE parent_asin NOT IN (SELECT parent_asin FROM listing)')[0]:,}",
    f"variant-ASIN reviews: {pct(q('SELECT count(*) FROM rev_clean WHERE is_variant_asin')[0], kept)}",
    f"reviews dated before listing launch: {bl[0]:,} on {bl[1]:,} listings (flagged before_launch, kept)",
    f"verified purchase: {pct(q('SELECT count(*) FROM rev_clean WHERE verified_purchase')[0], kept)}",
    f"date range: {dmin} to {dmax}",
])

# =============== Benchmarks -> shared layout ===============
B = RAW / "benchmarks"
bench_rows, pair_rows = [], []
spec = {
    "walmart_amazon": ("Walmart-Amazon", "walmart", "amazon", "title", "brand", "modelno", "category"),
    "abt_buy": ("Abt-Buy", "abt", "buy", "name", None, None, None),
    "amazon_google": ("Amazon-Google", "amazon", "google", "title", "manufacturer", None, None),
}
for ds, (folder, left, right, tcol, bcol, mcol, ccol) in spec.items():
    for side, retailer, fname in (("left", left, "source_source"), ("right", right, "target_target")):
        t = pd.read_parquet(B / folder / f"{fname}.parquet")
        for r in t.itertuples(index=False):
            r = r._asdict()
            title = R.clean_str(r[tcol])
            mcol_val = R.norm_modelno(r[mcol]) if mcol else None
            toks = R.generic_model_tokens(title)
            bench_rows.append(dict(
                dataset=ds, side=side, retailer=retailer, record_id=str(r["id"]), title=title,
                title_norm=R.norm_text(title), brand=R.norm_brand(r[bcol]) if bcol else None,
                model_no=mcol_val or (toks[0] if len(toks) == 1 else None),
                model_source="column" if mcol_val else ("title_single_token" if len(toks) == 1 else None),
                title_model_tokens=toks, category=R.clean_str(r[ccol]) if ccol else None,
                description=R.clean_str(r.get("description")), price=R.parse_price(r["price"]),
            ))
    for split in ("train", "valid", "test"):
        p = pd.read_parquet(B / folder / f"pairs_{split}.parquet")
        for r in p.itertuples(index=False):
            pair_rows.append(dict(dataset=ds, split=split, left_id=str(r.ltable_id), right_id=str(r.rtable_id), label=int(r.label)))
BL, BP = pd.DataFrame(bench_rows), pd.DataFrame(pair_rows)
BL.to_parquet(CLEAN / "bench_listing.parquet", index=False)
BP.to_parquet(CLEAN / "bench_pair.parquet", index=False)
lines = []
for ds, g in BL.groupby("dataset"):
    lines.append(f"{ds}: {len(g):,} rows; brand {pct(g.brand.notna().sum(), len(g))}; model_no {pct(g.model_no.notna().sum(), len(g))}; price {pct(g.price.notna().sum(), len(g))}")
for ds, g in BP.groupby("dataset"):
    lines.append(f"{ds} pairs: {len(g):,} ({g.label.sum():,} matches); " + ", ".join(f"{s} {len(x):,}" for s, x in g.groupby('split')))
log("Benchmarks (shared layout)", lines)

pr = pd.read_parquet(B / "product-matching" / "default_train.parquet")
PR = pd.DataFrame(dict(
    offer_id=pr["Product ID"].astype(str), vendor_id=pr["Vendor ID"].astype(str), cluster_id=pr["Cluster ID"].astype(str),
    title=pr["Product Title"].map(R.clean_str), title_norm=pr["Product Title"].map(R.norm_text),
    title_model_tokens=pr["Product Title"].map(R.generic_model_tokens), cluster_label=pr["Cluster Label"],
    category=pr["Category Label"],
))
PR.to_parquet(CLEAN / "pricerunner_offer.parquet", index=False)
log("PriceRunner", [f"offers {len(PR):,}; clusters {PR.cluster_id.nunique():,}; with a model-like token {pct((PR.title_model_tokens.map(len) > 0).sum(), len(PR))}"])

(CLEAN / "cleaning_report.md").write_text(
    f"# Cleaning report\n\nGenerated by `pipeline/clean.py` on {datetime.now():%Y-%m-%d %H:%M}. Raw inputs untouched.\n" + "".join(report) + "\n")
print("\nwrote", *sorted(p.name for p in CLEAN.iterdir()))

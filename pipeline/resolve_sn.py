"""Phase 4.2: give every SharkNinja listing a canonical product_id.

  1. model_key   : listings with a high/medium-confidence model number group by core_model (main units,
                   'SN-<core>') or base_model (accessories, separate 'SN-P-<base>' namespace so a part never
                   joins the machine it fits).
  2. title_match : remaining main units scored against keyed products in the same brand + product-type block
                   (matcher weights/threshold transferred from the Walmart-Amazon benchmark).
                   Accessories only link on an identical normalised title (fuzzy matching merged different parts).
  3. title_cluster: leftovers clustered among themselves with the same rules.
  4. singleton   : no confident match -> own product_id, written to sn_unmatched.parquet for review.
Unrelated listings (maker='unrelated') get no product_id.
Run: .venv/bin/python pipeline/resolve_sn.py"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import match as M  # noqa: E402
import rules as R  # noqa: E402

CLEAN = ROOT / "data/clean"
bench = json.loads((ROOT / "eval/bench_results.json").read_text())["walmart_amazon"]
W, THRESH = bench["weights"], bench["threshold"]

L = pd.read_parquet(CLEAN / "sn_listing.parquet")
nn = lambda v: None if v is None or (isinstance(v, float) and v != v) else v


def is_acc(r):
    return r.product_type == "accessory/part"


def key_of(r):
    if is_acc(r):
        return f"SN-P-{r.base_model}"
    return f"SN-{r.core_model}" + ("-SE" if r.self_empty else "")


def rec(r):
    return dict(title_norm=R.norm_text(r.title), model_no=(nn(r.core_model) or "").lower() or None,
                title_model_tokens=R.generic_model_tokens(r.title), price=nn(r.price), brand=r.brand)


def block(r):
    return (r.brand, "accessory" if r.product_type == "accessory/part" else r.product_type)


L["block"] = [block(r) for r in L.itertuples()]
scope = L[L.maker != "unrelated"].copy()
assign = {}  # parent_asin -> (product_id, method, score, matched_to, reason)

# Bundles of two different products ("Stick Vacuum + Rocket Upright") stay their own product.
for r in scope[scope.product_type == "bundle"].itertuples():
    assign[r.parent_asin] = (f"SN-B-{r.parent_asin}", "bundle", None, None, "title joins two products with '+'")
scope = scope[scope.product_type != "bundle"]

# 1. model key
keyed = scope[scope.base_model.notna() & scope.model_confidence.isin(["high", "medium"])]
reps = {}
for r in keyed.itertuples():
    pid = key_of(r)
    assign[r.parent_asin] = (pid, "model_key", 1.0, None, f"{'base' if is_acc(r) else 'core'} model {pid.split('-')[-1]} ({r.model_source})")
    reps.setdefault(r.block, []).append((pid, r.parent_asin, rec(r)))


def pair_score(a, b):
    """Accessories: identical normalised title only. Main units: the benchmark-tuned scorer."""
    if is_acc(a) or is_acc(b):
        same = R.norm_text(a.title) == R.norm_text(b.title)
        return (1.0 if same else 0.0), ("identical_title" if same else "accessory_no_fuzzy"), {}
    return M.score_pair(rec(a), rec(b), W)


rep_rows = {r.parent_asin: r for r in keyed.itertuples()}

# 2. title match against keyed products
rest = scope[~scope.parent_asin.isin(assign)]
unmatched_rows = []
for r in rest.itertuples():
    best = (0.0, None, None, None, None)
    for pid, pasin, other in reps.get(r.block, []):
        s, why, f = pair_score(r, rep_rows[pasin])
        if s > best[0]:
            best = (s, pid, pasin, why, f)
    if best[0] >= THRESH:
        assign[r.parent_asin] = (best[1], "title_match", round(best[0], 3), best[2], f"{best[3]} {best[4]}")
    else:
        unmatched_rows.append((r, best))

# 3. cluster leftovers among themselves (union-find within block)
left = [r for r, _ in unmatched_rows]
parent = {r.parent_asin: r.parent_asin for r in left}


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


pair_best = {}
for i, a in enumerate(left):
    for b in left[i + 1:]:
        if a.block != b.block:
            continue
        s, why, f = pair_score(a, b)
        if s >= THRESH:
            parent[find(a.parent_asin)] = find(b.parent_asin)
            pair_best[a.parent_asin] = pair_best.get(a.parent_asin) or (s, b.parent_asin, why)
            pair_best[b.parent_asin] = pair_best.get(b.parent_asin) or (s, a.parent_asin, why)
clusters = {}
for r in left:
    clusters.setdefault(find(r.parent_asin), []).append(r)
unmatched_out = []
for root, rs in clusters.items():
    if len(rs) > 1:
        pid = f"SN-C-{root}"
        for r in rs:
            s, other, why = pair_best[r.parent_asin]
            assign[r.parent_asin] = (pid, "title_cluster", round(s, 3), other, why)
    else:
        r = rs[0]
        best = next(b for x, b in unmatched_rows if x.parent_asin == r.parent_asin)
        assign[r.parent_asin] = (f"SN-A-{r.parent_asin}", "singleton", round(best[0], 3), best[2], "no candidate above threshold")
        unmatched_out.append(dict(parent_asin=r.parent_asin, title=r.title, segment=r.segment, product_type=r.product_type,
                                  model_no=nn(r.model_no), model_confidence=r.model_confidence, best_candidate_product=best[1],
                                  best_candidate_asin=best[2], best_score=round(best[0], 3), best_reason=best[3]))

for r in L[L.maker == "unrelated"].itertuples():
    assign[r.parent_asin] = (None, "excluded_unrelated", None, None, "maker=unrelated")

LP = pd.DataFrame([dict(parent_asin=k, product_id=v[0], link_method=v[1], link_score=v[2], matched_to=v[3], link_reason=v[4])
                   for k, v in assign.items()])
LP = LP.merge(L[["parent_asin", "segment", "maker", "product_type", "brand", "base_model", "core_model", "title", "rating_count",
                 "date_first_available", "average_rating"]], on="parent_asin")
LP.to_parquet(CLEAN / "sn_listing_product.parquet", index=False)
pd.DataFrame(unmatched_out).to_parquet(CLEAN / "sn_unmatched.parquet", index=False)

# product table
lp = LP[LP.product_id.notna()].copy()
lp["_bs"] = lp.segment == "brand_store"
lp["date_first_available"] = pd.to_datetime(lp["date_first_available"])
canon = lp.sort_values(["_bs", "rating_count"], ascending=False).drop_duplicates("product_id").set_index("product_id")
P = lp.groupby("product_id").agg(
    n_listings=("parent_asin", "count"), n_brand_store=("_bs", "sum"),
    n_renewed=("segment", lambda s: (s == "renewed").sum()),
    launch_date=("date_first_available", "min"), total_rating_count=("rating_count", "sum"),
    link_methods=("link_method", lambda s: ",".join(sorted(set(s)))),
).reset_index()
P = P.merge(canon[["title", "brand", "product_type", "maker"]].rename(columns={"title": "canonical_title"}), left_on="product_id", right_index=True)
P["model_key"] = P.product_id.where(~P.product_id.str.startswith(("SN-A-", "SN-C-", "SN-B-"))).str.replace(r"^SN-(P-)?|-SE$", "", regex=True)
P["self_empty_variant"] = P.product_id.str.endswith("-SE")
P["is_accessory"] = P.product_id.str.startswith("SN-P-") | (P.product_type == "accessory/part")
P.to_parquet(CLEAN / "sn_product.parquet", index=False)

n = len(L)
inscope = LP[LP.link_method != "excluded_unrelated"]
bs = inscope[inscope.segment == "brand_store"]
rn = inscope[inscope.segment == "renewed"]
linked = lambda d: d.link_method.isin(["model_key", "title_match", "title_cluster"]).sum()
inscope = inscope[inscope.link_method != "bundle"]
rn_to_bs = rn.product_id.isin(set(bs.product_id)).sum()
lines = [
    f"transferred matcher: weights {W}, threshold {THRESH} (tuned on Walmart-Amazon train+valid)",
    "link_method: " + ", ".join(f"{k} {v:,}" for k, v in LP.link_method.value_counts().items()),
    f"listings in scope: {len(inscope):,}; linked (not singleton): {linked(inscope):,} ({100 * linked(inscope) / len(inscope):.1f}%)",
    f"brand store linked or keyed: {linked(bs):,} / {len(bs):,}; renewed: {linked(rn):,} / {len(rn):,}",
    f"renewed listings sharing a product_id with a brand-store listing: {rn_to_bs:,} / {len(rn):,} ({100 * rn_to_bs / len(rn):.1f}%)",
    f"products: {len(P):,} (from {len(inscope):,} listings); multi-listing products: {(P.n_listings > 1).sum():,}; with both brand-store and renewed: {((P.n_brand_store > 0) & (P.n_renewed > 0)).sum():,}",
    f"singletons written to sn_unmatched.parquet: {len(unmatched_out):,}",
]
print("\n".join(lines))
(CLEAN / "resolution_report.md").write_text("# Entity resolution report (pipeline/resolve_sn.py)\n\n" + "\n".join(f"- {l}" for l in lines) + "\n")

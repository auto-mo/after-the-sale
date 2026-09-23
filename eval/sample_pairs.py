"""Draw a stratified, blind-labelling sample of SharkNinja listing pairs from the CURRENT resolution.
Strata: A model_key links, B title_match links, C title_cluster links, D hard negatives (same block,
different product, high title overlap), E near misses (singletons with a close best candidate).
Pairs already present in any earlier eval/*_key.csv are excluded.
usage: .venv/bin/python eval/sample_pairs.py <set_name> <seed>"""
import glob
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import match as M  # noqa: E402
import rules as R  # noqa: E402

SET, SEED = sys.argv[1], int(sys.argv[2])
random.seed(SEED)
seen = set()
for f in glob.glob(str(ROOT / "eval/*_key.csv")):
    if Path(f).name != f"{SET}_key.csv":
        for r in pd.read_csv(f).itertuples():
            seen.add(tuple(sorted((r.a_asin, r.b_asin))))

LP = pd.read_parquet(ROOT / "data/clean/sn_listing_product.parquet")
L = pd.read_parquet(ROOT / "data/clean/sn_listing.parquet").set_index("parent_asin")
raw = {json.loads(l)["parent_asin"]: json.loads(l) for l in open(ROOT / "data/raw/amazon2023/meta_sharkninja.jsonl")}
ins = LP[LP.product_id.notna()]
pid = ins.set_index("parent_asin").product_id
pairs = []


def add(a, b, stratum):
    k = tuple(sorted((a, b)))
    if a != b and isinstance(b, str) and k not in seen:
        seen.add(k)
        pairs.append((a, b, stratum))


groups = [g for g in ins[ins.link_method == "model_key"].groupby("product_id").parent_asin.apply(list) if len(g) > 1]
random.shuffle(groups)
for g in groups[:40]:
    a, b = random.sample(g, 2)
    add(a, b, "A_model_key")
for r in ins[ins.link_method == "title_match"].sample(frac=1, random_state=SEED).head(30).itertuples():
    add(r.parent_asin, r.matched_to, "B_title_match")
for r in ins[ins.link_method == "title_cluster"].sample(frac=1, random_state=SEED).head(20).itertuples():
    add(r.parent_asin, r.matched_to, "C_title_cluster")

X = L.loc[ins.parent_asin].assign(pid=pid)
X["tok"] = [M.tokens(R.norm_text(t)) for t in X.title]
X["blk"] = [(b, "acc" if p == "accessory/part" else p) for b, p in zip(X.brand, X.product_type)]
cand = []
for _, g in X.groupby("blk"):
    idx = list(g.index)
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            a, b = g.loc[idx[i]], g.loc[idx[j]]
            if a.pid != b.pid:
                jac = M.jaccard(a.tok, b.tok)
                if jac >= 0.45:
                    cand.append((idx[i], idx[j]))
random.shuffle(cand)
n0 = len(pairs)
for a, b in cand:
    if len(pairs) - n0 >= 40:
        break
    add(a, b, "D_hard_negative")
U = pd.read_parquet(ROOT / "data/clean/sn_unmatched.parquet")
U = U[(U.best_score >= 0.35) & U.best_candidate_asin.notna()].sample(frac=1, random_state=SEED)
n0 = len(pairs)
for r in U.itertuples():
    if len(pairs) - n0 >= 20:
        break
    add(r.parent_asin, r.best_candidate_asin, "E_near_miss")


def info(a):
    d = raw[a]
    det = d.get("details") or {}
    return dict(title=d["title"], item_model_number=det.get("Item model number"), model_name=det.get("Model Name"), store=d["store"],
                category=" > ".join(d.get("categories") or [])[-80:], features=" | ".join((d.get("features") or [])[:3])[:300])


random.shuffle(pairs)
rows, key = [], []
for i, (a, b, s) in enumerate(pairs):
    rows.append(dict(pair_id=i, a_asin=a, **{f"a_{k}": v for k, v in info(a).items()}, b_asin=b, **{f"b_{k}": v for k, v in info(b).items()}))
    key.append(dict(pair_id=i, a_asin=a, b_asin=b, stratum=s))
pd.DataFrame(rows).to_csv(ROOT / f"eval/{SET}_candidates.csv", index=False)
pd.DataFrame(key).to_csv(ROOT / f"eval/{SET}_key.csv", index=False)
print(SET, len(pairs), pd.DataFrame(key).stratum.value_counts().to_dict())

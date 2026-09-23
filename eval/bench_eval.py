"""Phase 4.1: tune the matcher on train+valid pairs, report precision/recall on held-out test pairs.
Writes eval/bench_results.md and eval/bench_results.json. Run: .venv/bin/python eval/bench_eval.py"""
import itertools
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import match as M  # noqa: E402

L = pd.read_parquet(ROOT / "data/clean/bench_listing.parquet")
P = pd.read_parquet(ROOT / "data/clean/bench_pair.parquet")
nn = lambda v: None if v is None or (isinstance(v, float) and v != v) else v
recs = {(r.dataset, r.side, r.record_id): dict(title_norm=r.title_norm, model_no=nn(r.model_no), title_model_tokens=list(r.title_model_tokens),
                                                 price=nn(r.price), brand=nn(r.brand)) for r in L.itertuples()}


def metrics(y, yhat):
    tp = sum(1 for a, b in zip(y, yhat) if a and b)
    fp = sum(1 for a, b in zip(y, yhat) if not a and b)
    fn = sum(1 for a, b in zip(y, yhat) if a and not b)
    tn = len(y) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return dict(precision=round(p, 3), recall=round(r, 3), f1=round(2 * p * r / (p + r), 3) if p + r else 0.0, tp=tp, fp=fp, fn=fn, tn=tn)


grid = dict(jac=[1.0], cross=[0.0, 0.2, 0.35, 0.5, 0.8], price=[0.0, 0.15, 0.25, 0.4], brand=[0.0, 0.1, 0.2], num=[0.0, 0.1, 0.2, 0.3])
thresholds = [x / 100 for x in range(20, 91, 2)]
out, md = {}, ["# Benchmark matcher results", "",
               "Weights and threshold tuned on train+valid only; metrics below are on the held-out **test** split.", ""]
for ds, g in P.groupby("dataset"):
    pairs = [(r.split, r.label, recs[(ds, "left", r.left_id)], recs[(ds, "right", r.right_id)]) for r in g.itertuples()]
    tune = [p for p in pairs if p[0] != "test"]
    test = [p for p in pairs if p[0] == "test"]
    best = None
    for jac, cross, price, brand, num in itertools.product(*grid.values()):
        w = dict(jac=jac, cross=cross, price=price, brand=brand, num=num)
        scores = [M.score_pair(a, b, w)[0] for _, _, a, b in tune]
        y = [lab == 1 for _, lab, _, _ in tune]
        for t in thresholds:
            m = metrics(y, [s >= t for s in scores])
            if best is None or m["f1"] > best[0]["f1"]:
                best = (m, w, t)
    tm, w, t = best
    scored = [(lab == 1, *M.score_pair(a, b, w)) for _, lab, a, b in test]
    m = metrics([s[0] for s in scored], [s[1] >= t for s in scored])
    reasons = pd.Series([s[2] for s in scored]).value_counts().to_dict()
    # Baselines on the same test split.
    base_model = metrics([s[0] for s in scored], [s[3]["model_relation"] == "equal" for s in scored])
    jac_only = max((metrics([s[0] for s in scored], [s[3]["jaccard"] >= x for s in scored]) for x in thresholds), key=lambda d: d["f1"])
    out[ds] = dict(weights=w, threshold=t, tune=tm, test=m, test_reasons=reasons, baseline_model_only=base_model, baseline_title_only_best=jac_only)
    md += [f"## {ds}", f"- tuned weights {w}, threshold {t}",
           f"- **test: precision {m['precision']}, recall {m['recall']}, F1 {m['f1']}** (tp {m['tp']}, fp {m['fp']}, fn {m['fn']}, tn {m['tn']})",
           f"- baseline model-number only: precision {base_model['precision']}, recall {base_model['recall']}, F1 {base_model['f1']}",
           f"- baseline title overlap only (best threshold chosen on test, so optimistic): F1 {jac_only['f1']}",
           f"- decision path on test pairs: {reasons}", ""]
    print(ds, "test", m, "| model-only F1", base_model["f1"], "| title-only F1", jac_only["f1"])
(ROOT / "eval/bench_results.json").write_text(json.dumps(out, indent=2))
(ROOT / "eval/bench_results.md").write_text("\n".join(md))

"""Phase 4.3: score SharkNinja resolution against blind hand labels.
The sample is stratified by decision type, so results are reported per stratum:
  A/B/C (matcher said same)      -> precision of each linking method
  D/E   (matcher said different) -> how many true matches the matcher missed among the hardest cases
Run: .venv/bin/python eval/sn_eval.py"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
# usage: sn_eval.py [set_name]  -> reads eval/<set>_key.csv, eval/<set>_labels.csv (default sn_truth = dev set)
SET = sys.argv[1] if len(sys.argv) > 1 else "sn_truth"
key = pd.read_csv(ROOT / f"eval/{SET}_key.csv")
lab = pd.read_csv(ROOT / f"eval/{SET}_labels.csv")
# Predictions always come from the CURRENT resolution; strata are from sampling time.
pid = pd.read_parquet(ROOT / "data/clean/sn_listing_product.parquet").set_index("parent_asin").product_id
key["predicted_same"] = [pd.notna(pid.get(a)) and pid.get(a) == pid.get(b) for a, b in zip(key.a_asin, key.b_asin)]
lab["label"] = lab["label"].astype(str).str.strip().str.lower()
df = key.merge(lab, on="pair_id", how="left")
assert df["label"].notna().all(), "missing labels"
df["truth"] = df["label"].map({"1": True, "0": False, "1.0": True, "0.0": False})
lines = [f"# SharkNinja matcher evaluation (blind labels, set: {SET})", "",
         f"Pairs: {len(df)}; unsure: {(df.truth.isna()).sum()} (excluded from metrics).", "",
         "| Stratum | Matcher said | Pairs (labelled) | Truly same | Truly different | Accuracy of matcher decision |", "|---|---|---|---|---|---|"]
for s, g in df.groupby("stratum"):
    g = g[g.truth.notna()]
    said = f"same {g.predicted_same.sum()} / diff {(~g.predicted_same).sum()}"
    correct = (g.truth == g.predicted_same).sum()
    lines.append(f"| {s} | {said} | {len(g)} | {g.truth.sum()} | {(~g.truth.astype(bool)).sum()} | {correct}/{len(g)} ({100 * correct / len(g):.0f}%) |")
d = df[df.truth.notna()]
tp = (d.predicted_same & d.truth.astype(bool)).sum()
fp = (d.predicted_same & ~d.truth.astype(bool)).sum()
fn = (~d.predicted_same & d.truth.astype(bool)).sum()
tn = (~d.predicted_same & ~d.truth.astype(bool)).sum()
lines += ["", f"Pooled over the sample (not population rates, because strata are not proportional): "
              f"precision {tp / (tp + fp):.3f}, recall on sampled pairs {tp / (tp + fn):.3f} (tp {tp}, fp {fp}, fn {fn}, tn {tn}).", "",
          "## Disagreements", ""]
for r in df[df.truth.notna() & (df.truth.astype(bool) != df.predicted_same)].itertuples():
    lines.append(f"- pair {r.pair_id} [{r.stratum}] matcher={'same' if r.predicted_same else 'diff'}, label={r.label} ({r.confidence}): {r.rationale}")
(ROOT / f"eval/{SET}_results.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
